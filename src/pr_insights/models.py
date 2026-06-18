"""Data models for PR Insights."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PRState(str, Enum):
    """Pull request states."""

    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


class ReviewState(str, Enum):
    """Pull request review states."""

    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    COMMENTED = "COMMENTED"
    DISMISSED = "DISMISSED"


class PRReview(BaseModel):
    """Pull request review."""

    reviewer: str
    state: ReviewState
    submitted_at: datetime
    body: str | None = None


class PRCommit(BaseModel):
    """Pull request commit."""

    sha: str
    message: str
    author: str
    committed_at: datetime


class PullRequest(BaseModel):
    """Pull request with computed properties."""

    number: int
    title: str
    state: PRState
    author: str
    created_at: datetime
    updated_at: datetime
    merged_at: datetime | None = None
    merged_by: str | None = None
    labels: list[str] = Field(default_factory=list)
    reviews: list[PRReview] = Field(default_factory=list)
    commits: list[PRCommit] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    base_ref: str = "main"
    head_ref: str = ""

    @property
    def is_open(self) -> bool:
        return self.state == PRState.OPEN

    @property
    def is_closed(self) -> bool:
        return self.state in (PRState.CLOSED, PRState.MERGED)

    @property
    def is_merged(self) -> bool:
        return self.state in (PRState.CLOSED, PRState.MERGED) and self.merged_at is not None

    @property
    def has_approval(self) -> bool:
        return any(r.state == ReviewState.APPROVED for r in self.reviews)

    @property
    def has_changes_requested(self) -> bool:
        return any(r.state == ReviewState.CHANGES_REQUESTED for r in self.reviews)

    @property
    def time_to_first_review(self) -> float | None:
        """Time in seconds from PR creation to first non-dismissed review."""
        non_dismissed = [r for r in self.reviews if r.state != ReviewState.DISMISSED]
        if not non_dismissed:
            return None
        first_review = min(non_dismissed, key=lambda r: r.submitted_at)
        return (first_review.submitted_at - self.created_at).total_seconds()

    @property
    def time_to_merge(self) -> float | None:
        """Time in seconds from PR creation to merge."""
        if not self.is_merged or self.merged_at is None:
            return None
        return (self.merged_at - self.created_at).total_seconds()


class ContributorStat(BaseModel):
    """Statistics for a single contributor."""

    login: str
    total_prs: int = 0
    merged_prs: int = 0
    open_prs: int = 0
    closed_prs: int = 0
    total_additions: int = 0
    total_deletions: int = 0

    @property
    def merge_rate(self) -> float:
        if self.total_prs == 0:
            return 0.0
        return self.merged_prs / self.total_prs


class ContributorStats(BaseModel):
    """Aggregated contributor statistics."""

    contributors: dict[str, ContributorStat] = Field(default_factory=dict)

    @classmethod
    def from_prs(cls, prs: list[PullRequest]) -> "ContributorStats":
        """Create ContributorStats from a list of PRs."""
        contributors: dict[str, ContributorStat] = {}
        for pr in prs:
            if pr.author not in contributors:
                contributors[pr.author] = ContributorStat(login=pr.author)
            stat = contributors[pr.author]
            stat.total_prs += 1
            stat.total_additions += pr.additions
            stat.total_deletions += pr.deletions
            if pr.is_open:
                stat.open_prs += 1
            elif pr.is_merged:
                stat.merged_prs += 1
                stat.closed_prs += 1
            else:
                stat.closed_prs += 1
        return cls(contributors=contributors)


class PRStats(BaseModel):
    """Aggregated PR statistics."""

    prs: list[PullRequest]

    @property
    def total_prs(self) -> int:
        return len(self.prs)

    @property
    def merged_prs(self) -> int:
        return sum(1 for pr in self.prs if pr.is_merged)

    @property
    def open_prs(self) -> int:
        return sum(1 for pr in self.prs if pr.is_open)

    @property
    def closed_prs(self) -> int:
        return sum(1 for pr in self.prs if pr.is_closed)

    @property
    def merge_rate(self) -> float:
        if self.total_prs == 0:
            return 0.0
        return self.merged_prs / self.total_prs

    @property
    def avg_time_to_merge(self) -> float | None:
        times = [
            pr.time_to_merge for pr in self.prs if pr.is_merged and pr.time_to_merge is not None
        ]
        if not times:
            return None
        return sum(times) / len(times)

    @property
    def avg_time_to_first_review(self) -> float | None:
        times = [pr.time_to_first_review for pr in self.prs if pr.time_to_first_review is not None]
        if not times:
            return None
        return sum(times) / len(times)
