"""GitHub API client for PR Insights."""

import asyncio
import os
from datetime import datetime

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from pr_insights.models import PRCommit, PRReview, PRState, PullRequest, ReviewState


class GitHubAPIError(Exception):
    """Base exception for GitHub API errors."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class RateLimitError(GitHubAPIError):
    """Raised when API rate limit is exceeded."""

    def __init__(self, reset_time: int | None = None):
        super().__init__("GitHub API rate limit exceeded", 403)
        self.reset_time = reset_time


class GitHubClient:
    """Async GitHub API client with rate limit handling and retries."""

    BASE_URL = "https://api.github.com/"

    def __init__(
        self,
        token: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError(
                "GitHub token required. Set GITHUB_TOKEN env var or pass token parameter."
            )

        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "pr-insights/0.1.0",
        }

    async def __aenter__(self) -> "GitHubClient":
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=self._headers,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers=self._headers,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _parse_next_link(self, link_header: str) -> str | None:
        """Parse Link header to find next page URL."""
        if not link_header:
            return None
        for part in link_header.split(","):
            part = part.strip()
            if 'rel="next"' in part:
                start = part.find("<") + 1
                end = part.find(">")
                if start > 0 and end > start:
                    return part[start:end]
        return None

    def _handle_error_response(self, response: httpx.Response) -> None:
        """Handle error responses and raise appropriate exceptions."""
        if response.status_code == 403:
            remaining = response.headers.get("X-RateLimit-Remaining")
            if remaining == "0":
                reset_time = response.headers.get("X-RateLimit-Reset")
                raise RateLimitError(reset_time=int(reset_time) if reset_time else None)
        elif response.status_code == 404:
            raise GitHubAPIError("Resource not found", 404)
        elif response.status_code == 401:
            raise GitHubAPIError("Authentication failed", 401)
        response.raise_for_status()

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
    )
    async def _get(self, url: str, params: dict | None = None) -> httpx.Response:
        """GET request with retry logic."""
        response = await self.client.get(url, params=params)
        self._handle_error_response(response)
        return response

    async def get_prs(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        per_page: int = 100,
        max_pages: int | None = None,
    ) -> list[PullRequest]:
        """Fetch all PRs for a repository."""
        url = f"repos/{owner}/{repo}/pulls"
        params = {"state": state, "per_page": per_page, "sort": "updated", "direction": "desc"}
        all_prs = []
        page = 0

        while True:
            if max_pages and page >= max_pages:
                break

            response = await self._get(url, params=params)
            prs_data = response.json()

            if not prs_data:
                break

            for pr_data in prs_data:
                pr = self._parse_pr(pr_data)
                all_prs.append(pr)

            next_url = self._parse_next_link(response.headers.get("Link", ""))
            if not next_url:
                break

            url = next_url.replace(self.BASE_URL, "")
            params = None  # URL already contains params
            page += 1

        return all_prs

    async def get_pr(self, owner: str, repo: str, number: int) -> PullRequest:
        """Fetch a single PR with full details."""
        response = await self._get(f"repos/{owner}/{repo}/pulls/{number}")
        pr_data = response.json()

        # Enrich with additional data
        pr = self._parse_pr(pr_data)

        # Fetch reviews, commits if not in initial response
        if "reviews" not in pr_data:
            reviews = await self.get_pr_reviews(owner, repo, number)
            pr.reviews = reviews

        if "commits" not in pr_data:
            commits = await self.get_pr_commits(owner, repo, number)
            pr.commits = commits

        return pr

    async def get_pr_reviews(self, owner: str, repo: str, number: int) -> list[PRReview]:
        """Fetch reviews for a PR."""
        response = await self._get(f"repos/{owner}/{repo}/pulls/{number}/reviews")
        reviews_data = response.json()

        reviews = []
        for review_data in reviews_data:
            if review_data.get("user") and review_data.get("state"):
                reviews.append(
                    PRReview(
                        reviewer=review_data["user"]["login"],
                        state=ReviewState(review_data["state"]),
                        submitted_at=datetime.fromisoformat(
                            review_data["submitted_at"].replace("Z", "+00:00")
                        ),
                        body=review_data.get("body"),
                    )
                )
        return reviews

    async def get_pr_commits(self, owner: str, repo: str, number: int) -> list[PRCommit]:
        """Fetch commits for a PR."""
        response = await self._get(f"repos/{owner}/{repo}/pulls/{number}/commits")
        commits_data = response.json()

        commits = []
        for commit_data in commits_data:
            commit_info = commit_data.get("commit", {})
            author_info = commit_info.get("author", {})
            commits.append(
                PRCommit(
                    sha=commit_data["sha"],
                    message=commit_info.get("message", ""),
                    author=author_info.get("name", "unknown"),
                    committed_at=datetime.fromisoformat(
                        author_info.get("date", "").replace("Z", "+00:00")
                    ),
                )
            )
        return commits

    def _parse_pr(self, data: dict) -> PullRequest:
        """Parse PR data from API response."""
        labels = [label["name"] for label in data.get("labels", [])]

        merged_at = None
        if data.get("merged_at"):
            merged_at = datetime.fromisoformat(data["merged_at"].replace("Z", "+00:00"))

        merged_by = None
        if data.get("merged_by"):
            merged_by = data["merged_by"]["login"]

        state = PRState(data["state"])
        if state == PRState.CLOSED and merged_at:
            state = PRState.MERGED

        return PullRequest(
            number=data["number"],
            title=data["title"],
            state=state,
            author=data["user"]["login"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            merged_at=merged_at,
            merged_by=merged_by,
            labels=labels,
            base_ref=data["base"]["ref"],
            head_ref=data["head"]["ref"],
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
            changed_files=data.get("changed_files", 0),
        )

    # Sync wrappers for convenience
    def get_prs_sync(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        per_page: int = 100,
        max_pages: int | None = None,
    ) -> list[PullRequest]:
        """Sync wrapper for get_prs."""
        return asyncio.run(self.get_prs(owner, repo, state, per_page, max_pages))

    def get_pr_sync(self, owner: str, repo: str, number: int) -> PullRequest:
        """Sync wrapper for get_pr."""
        return asyncio.run(self.get_pr(owner, repo, number))
