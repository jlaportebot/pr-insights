"""Tests for GitHub API client."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from pr_insights.github_client import GitHubAPIError, GitHubClient, RateLimitError
from pr_insights.models import PRState, PullRequest


class TestGitHubClient:
    """Tests for GitHubClient."""

    @pytest.fixture
    def client(self):
        """Create a client with a mock token."""
        client = GitHubClient(token="test-token")
        # Initialize the internal httpx client for mocking
        client._client = MagicMock(spec=httpx.AsyncClient)
        return client

    @pytest.fixture
    def mock_response(self):
        """Create a mock httpx response."""

        def _make_response(json_data, status_code=200, headers=None):
            response = MagicMock(spec=httpx.Response)
            response.status_code = status_code
            response.json.return_value = json_data
            response.headers = headers or {}
            response.raise_for_status = MagicMock()
            if status_code >= 400:
                response.raise_for_status.side_effect = httpx.HTTPStatusError(
                    "Error", request=MagicMock(), response=response
                )
            return response

        return _make_response

    @pytest.mark.asyncio
    async def test_get_pr_list(self, client, mock_response):
        """Test fetching PR list."""
        pr_data = [
            {
                "number": 42,
                "title": "Fix bug",
                "state": "open",
                "user": {"login": "johndoe"},
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
                "merged_at": None,
                "labels": [{"name": "bug"}],
                "base": {"ref": "main"},
                "head": {"ref": "fix-bug"},
            }
        ]
        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(pr_data)
            prs = await client.get_prs("owner", "repo", state="open")

        assert len(prs) == 1
        assert prs[0].number == 42
        assert prs[0].title == "Fix bug"
        assert prs[0].author == "johndoe"
        assert prs[0].state == PRState.OPEN

    @pytest.mark.asyncio
    async def test_get_pr_list_with_pagination(self, client, mock_response):
        """Test fetching PR list with pagination."""
        pr_data_page1 = [
            {
                "number": i,
                "title": f"PR {i}",
                "state": "open",
                "user": {"login": "user"},
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
                "merged_at": None,
                "labels": [],
                "base": {"ref": "main"},
                "head": {"ref": f"branch-{i}"},
            }
            for i in range(1, 51)
        ]
        pr_data_page2 = [
            {
                "number": i,
                "title": f"PR {i}",
                "state": "open",
                "user": {"login": "user"},
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
                "merged_at": None,
                "labels": [],
                "base": {"ref": "main"},
                "head": {"ref": f"branch-{i}"},
            }
            for i in range(51, 76)
        ]

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [
                mock_response(
                    pr_data_page1,
                    headers={
                        "Link": '<https://api.github.com/repos/owner/repo/pulls?page=2>; rel="next"'
                    },
                ),
                mock_response(pr_data_page2),
            ]
            prs = await client.get_prs("owner", "repo", state="open")

        assert len(prs) == 75
        assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def test_get_pr_details(self, client, mock_response):
        """Test fetching single PR details."""
        pr_data = {
            "number": 42,
            "title": "Fix bug",
            "state": "closed",
            "user": {"login": "johndoe"},
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-16T14:00:00Z",
            "merged_at": "2024-01-16T14:00:00Z",
            "merged_by": {"login": "janedoe"},
            "labels": [{"name": "bug"}, {"name": "backend"}],
            "base": {"ref": "main"},
            "head": {"ref": "fix-bug"},
            "additions": 100,
            "deletions": 50,
            "changed_files": 5,
        }
        reviews_data = []
        commits_data = []
        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [
                mock_response(pr_data),
                mock_response(reviews_data),
                mock_response(commits_data),
            ]
            pr = await client.get_pr("owner", "repo", 42)

        assert pr.number == 42
        assert pr.is_merged is True
        assert pr.merged_by == "janedoe"
        assert pr.additions == 100
        assert pr.deletions == 50

    @pytest.mark.asyncio
    async def test_get_pr_reviews(self, client, mock_response):
        """Test fetching PR reviews."""
        reviews_data = [
            {
                "user": {"login": "reviewer1"},
                "state": "APPROVED",
                "submitted_at": "2024-01-15T11:00:00Z",
                "body": "LGTM",
            },
            {
                "user": {"login": "reviewer2"},
                "state": "CHANGES_REQUESTED",
                "submitted_at": "2024-01-15T12:00:00Z",
                "body": "Please fix X",
            },
        ]
        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(reviews_data)
            reviews = await client.get_pr_reviews("owner", "repo", 42)

        assert len(reviews) == 2
        assert reviews[0].reviewer == "reviewer1"
        assert reviews[0].state.value == "APPROVED"
        assert reviews[1].reviewer == "reviewer2"
        assert reviews[1].state.value == "CHANGES_REQUESTED"

    @pytest.mark.asyncio
    async def test_get_pr_commits(self, client, mock_response):
        """Test fetching PR commits."""
        commits_data = [
            {
                "sha": "abc123",
                "commit": {
                    "message": "Fix auth bug",
                    "author": {"name": "johndoe", "date": "2024-01-15T10:30:00Z"},
                },
            }
        ]
        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(commits_data)
            commits = await client.get_pr_commits("owner", "repo", 42)

        assert len(commits) == 1
        assert commits[0].sha == "abc123"
        assert commits[0].message == "Fix auth bug"

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, client, mock_response):
        """Test rate limit error handling."""
        response = mock_response({"message": "API rate limit exceeded"}, status_code=403)
        response.headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1234567890"}

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response
            with pytest.raises(RateLimitError):
                await client.get_prs("owner", "repo")

    @pytest.mark.asyncio
    async def test_not_found_error(self, client, mock_response):
        """Test 404 error handling."""
        response = mock_response({"message": "Not Found"}, status_code=404)

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response
            with pytest.raises(GitHubAPIError) as exc_info:
                await client.get_pr("owner", "repo", 999)

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_authentication_error(self, client, mock_response):
        """Test 401 error handling."""
        response = mock_response({"message": "Bad credentials"}, status_code=401)

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response
            with pytest.raises(GitHubAPIError) as exc_info:
                await client.get_prs("owner", "repo")

        assert "authentication" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_retry_on_server_error(self, client, mock_response):
        """Test retry on 5xx errors."""
        success_response = mock_response(
            [
                {
                    "number": 1,
                    "title": "Test",
                    "state": "open",
                    "user": {"login": "user"},
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-15T10:30:00Z",
                    "merged_at": None,
                    "labels": [],
                    "base": {"ref": "main"},
                    "head": {"ref": "branch"},
                }
            ]
        )
        error_response = mock_response({"message": "Internal Server Error"}, status_code=500)
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=error_response
        )

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [error_response, success_response]
            prs = await client.get_prs("owner", "repo")

        assert len(prs) == 1
        assert mock_get.call_count == 2

    def test_parse_link_header(self, client):
        """Test parsing Link header for pagination."""
        link = '<https://api.github.com/repos/owner/repo/pulls?page=2>; rel="next", <https://api.github.com/repos/owner/repo/pulls?page=5>; rel="last"'
        next_url = client._parse_next_link(link)
        assert next_url == "https://api.github.com/repos/owner/repo/pulls?page=2"

    def test_parse_link_header_no_next(self, client):
        """Test parsing Link header with no next page."""
        link = '<https://api.github.com/repos/owner/repo/pulls?page=5>; rel="last"'
        next_url = client._parse_next_link(link)
        assert next_url is None


class TestGitHubClientSync:
    """Tests for sync methods."""

    @pytest.fixture
    def client(self):
        return GitHubClient(token="test-token")

    def test_sync_get_prs(self, client):
        """Test sync wrapper for get_prs."""
        # This tests the sync wrapper works
        # We mock the async method directly

        async def mock_get_prs(*args, **kwargs):
            return [
                PullRequest(
                    number=1,
                    title="Test",
                    state=PRState.OPEN,
                    author="user",
                    created_at=datetime(2024, 1, 1),
                    updated_at=datetime(2024, 1, 1),
                )
            ]

        client.get_prs = mock_get_prs
        prs = client.get_prs_sync("owner", "repo")
        assert len(prs) == 1
        assert prs[0].number == 1
