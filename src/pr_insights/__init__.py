"""PR Insights - Analyze GitHub pull request patterns and generate insights."""

from pr_insights.analyzer import PRAnalyzer
from pr_insights.cli import main
from pr_insights.github_client import GitHubAPIError, GitHubClient, RateLimitError
from pr_insights.models import (
    ContributorStat,
    ContributorStats,
    PRCommit,
    PRReview,
    PRState,
    PRStats,
    PullRequest,
    ReviewState,
)

__version__ = "0.1.0"
__all__ = [
    "ContributorStat",
    "ContributorStats",
    "GitHubAPIError",
    "GitHubClient",
    "PRAnalyzer",
    "PRCommit",
    "PRReview",
    "PRState",
    "PRStats",
    "PullRequest",
    "RateLimitError",
    "ReviewState",
    "main",
]
