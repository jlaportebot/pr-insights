"""Tests for PR data models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from pr_insights.models import ContributorStats, PRCommit, PRReview, PRStats, PullRequest


class TestPullRequest:
    """Tests for PullRequest model."""

    def test_create_minimal_pr(self):
        """Test creating a PR with minimal required fields."""
        pr = PullRequest(
            number=42,
            title="Fix bug in auth",
            state="open",
            author="johndoe",
            created_at=datetime(2024, 1, 15, 10, 30),
            updated_at=datetime(2024, 1, 15, 10, 30),
        )
        assert pr.number == 42
        assert pr.title == "Fix bug in auth"
        assert pr.state == "open"
        assert pr.author == "johndoe"
        assert pr.is_open is True
        assert pr.is_merged is False
        assert pr.is_closed is False

    def test_pr_merged_state(self):
        """Test PR with merged state."""
        pr = PullRequest(
            number=42,
            title="Fix bug in auth",
            state="closed",
            author="johndoe",
            created_at=datetime(2024, 1, 15, 10, 30),
            updated_at=datetime(2024, 1, 16, 14, 0),
            merged_at=datetime(2024, 1, 16, 14, 0),
            merged_by="janedoe",
        )
        assert pr.is_merged is True
        assert pr.is_closed is True
        assert pr.is_open is False
        assert pr.merged_by == "janedoe"

    def test_pr_closed_not_merged(self):
        """Test PR closed without merge."""
        pr = PullRequest(
            number=42,
            title="WIP: experimental feature",
            state="closed",
            author="johndoe",
            created_at=datetime(2024, 1, 15, 10, 30),
            updated_at=datetime(2024, 1, 20, 10, 0),
            merged_at=None,
        )
        assert pr.is_closed is True
        assert pr.is_merged is False
        assert pr.is_open is False

    def test_pr_with_labels(self):
        """Test PR with labels."""
        pr = PullRequest(
            number=42,
            title="Fix bug",
            state="open",
            author="johndoe",
            created_at=datetime(2024, 1, 15, 10, 30),
            updated_at=datetime(2024, 1, 15, 10, 30),
            labels=["bug", "backend", "priority:high"],
        )
        assert "bug" in pr.labels
        assert len(pr.labels) == 3

    def test_pr_with_reviews(self):
        """Test PR with review data."""
        reviews = [
            PRReview(
                reviewer="reviewer1",
                state="APPROVED",
                submitted_at=datetime(2024, 1, 15, 11, 0),
            ),
            PRReview(
                reviewer="reviewer2",
                state="CHANGES_REQUESTED",
                submitted_at=datetime(2024, 1, 15, 12, 0),
            ),
        ]
        pr = PullRequest(
            number=42,
            title="Fix bug",
            state="open",
            author="johndoe",
            created_at=datetime(2024, 1, 15, 10, 30),
            updated_at=datetime(2024, 1, 15, 12, 0),
            reviews=reviews,
        )
        assert len(pr.reviews) == 2
        assert pr.reviews[0].state == "APPROVED"
        assert pr.has_approval is True
        assert pr.has_changes_requested is True

    def test_pr_review_time_calculation(self):
        """Test time to first review calculation."""
        pr = PullRequest(
            number=42,
            title="Fix bug",
            state="open",
            author="johndoe",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 15, 12, 0),
            reviews=[
                PRReview(
                    reviewer="reviewer1",
                    state="APPROVED",
                    submitted_at=datetime(2024, 1, 15, 11, 0),
                ),
            ],
        )
        assert pr.time_to_first_review == 3600  # 1 hour in seconds

    def test_pr_merge_time_calculation(self):
        """Test merge time calculation for merged PRs."""
        pr = PullRequest(
            number=42,
            title="Fix bug",
            state="closed",
            author="johndoe",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 16, 14, 0),
            merged_at=datetime(2024, 1, 16, 14, 0),
        )
        assert pr.time_to_merge == 28 * 3600  # 28 hours in seconds

    def test_pr_merge_time_none_for_open(self):
        """Test merge time is None for open PRs."""
        pr = PullRequest(
            number=42,
            title="Fix bug",
            state="open",
            author="johndoe",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 15, 12, 0),
        )
        assert pr.time_to_merge is None

    def test_invalid_state_raises(self):
        """Test that invalid state raises validation error."""
        with pytest.raises(ValidationError):
            PullRequest(
                number=42,
                title="Fix bug",
                state="invalid",
                author="johndoe",
                created_at=datetime(2024, 1, 15, 10, 30),
                updated_at=datetime(2024, 1, 15, 10, 30),
            )


class TestPRReview:
    """Tests for PRReview model."""

    def test_review_creation(self):
        """Test creating a review."""
        review = PRReview(
            reviewer="reviewer1",
            state="APPROVED",
            submitted_at=datetime(2024, 1, 15, 11, 0),
            body="LGTM",
        )
        assert review.reviewer == "reviewer1"
        assert review.state == "APPROVED"
        assert review.body == "LGTM"

    def test_review_states(self):
        """Test all valid review states."""
        for state in ["APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED"]:
            review = PRReview(
                reviewer="reviewer1",
                state=state,
                submitted_at=datetime(2024, 1, 15, 11, 0),
            )
            assert review.state == state


class TestPRCommit:
    """Tests for PRCommit model."""

    def test_commit_creation(self):
        """Test creating a commit."""
        commit = PRCommit(
            sha="abc123",
            message="Fix authentication bug",
            author="johndoe",
            committed_at=datetime(2024, 1, 15, 10, 30),
        )
        assert commit.sha == "abc123"
        assert commit.message == "Fix authentication bug"


class TestPRStats:
    """Tests for PRStats aggregated statistics."""

    def test_pr_stats_empty(self):
        """Test stats with empty PR list."""
        stats = PRStats(prs=[])
        assert stats.total_prs == 0
        assert stats.merged_prs == 0
        assert stats.open_prs == 0
        assert stats.closed_prs == 0
        assert stats.merge_rate == 0.0
        assert stats.avg_time_to_merge is None
        assert stats.avg_time_to_first_review is None

    def test_pr_stats_with_data(self):
        """Test stats calculation with PR data."""
        prs = [
            PullRequest(
                number=1,
                title="PR 1",
                state="closed",
                author="alice",
                created_at=datetime(2024, 1, 1, 10, 0),
                updated_at=datetime(2024, 1, 2, 10, 0),
                merged_at=datetime(2024, 1, 2, 10, 0),
                reviews=[
                    PRReview(
                        reviewer="bob",
                        state="APPROVED",
                        submitted_at=datetime(2024, 1, 1, 12, 0),
                    )
                ],
            ),
            PullRequest(
                number=2,
                title="PR 2",
                state="open",
                author="bob",
                created_at=datetime(2024, 1, 5, 10, 0),
                updated_at=datetime(2024, 1, 5, 10, 0),
            ),
            PullRequest(
                number=3,
                title="PR 3",
                state="closed",
                author="alice",
                created_at=datetime(2024, 1, 10, 10, 0),
                updated_at=datetime(2024, 1, 11, 10, 0),
                merged_at=None,  # closed without merge
            ),
        ]
        stats = PRStats(prs=prs)
        assert stats.total_prs == 3
        assert stats.merged_prs == 1
        assert stats.open_prs == 1
        assert stats.closed_prs == 2
        assert stats.merge_rate == 1 / 3
        assert stats.avg_time_to_merge == 24 * 3600  # 24 hours
        assert stats.avg_time_to_first_review == 2 * 3600  # 2 hours


class TestContributorStats:
    """Tests for ContributorStats."""

    def test_contributor_stats(self):
        """Test contributor statistics calculation."""
        prs = [
            PullRequest(
                number=1,
                title="PR 1",
                state="closed",
                author="alice",
                created_at=datetime(2024, 1, 1, 10, 0),
                updated_at=datetime(2024, 1, 2, 10, 0),
                merged_at=datetime(2024, 1, 2, 10, 0),
            ),
            PullRequest(
                number=2,
                title="PR 2",
                state="closed",
                author="alice",
                created_at=datetime(2024, 1, 5, 10, 0),
                updated_at=datetime(2024, 1, 6, 10, 0),
                merged_at=datetime(2024, 1, 6, 10, 0),
            ),
            PullRequest(
                number=3,
                title="PR 3",
                state="open",
                author="bob",
                created_at=datetime(2024, 1, 10, 10, 0),
                updated_at=datetime(2024, 1, 10, 10, 0),
            ),
        ]
        stats = ContributorStats.from_prs(prs)
        assert len(stats.contributors) == 2
        assert stats.contributors["alice"].total_prs == 2
        assert stats.contributors["alice"].merged_prs == 2
        assert stats.contributors["alice"].open_prs == 0
        assert stats.contributors["bob"].total_prs == 1
        assert stats.contributors["bob"].merged_prs == 0
        assert stats.contributors["bob"].open_prs == 1


class TestModelsEdgeCases:
    """Edge case tests for models."""

    def test_pr_with_no_reviews(self):
        """Test PR with no reviews has correct defaults."""
        pr = PullRequest(
            number=1,
            title="Test",
            state="open",
            author="author",
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
        )
        assert pr.reviews == []
        assert pr.has_approval is False
        assert pr.has_changes_requested is False
        assert pr.time_to_first_review is None

    def test_pr_with_dismissed_review(self):
        """Test that dismissed reviews don't count as approval."""
        pr = PullRequest(
            number=1,
            title="Test",
            state="open",
            author="author",
            created_at=datetime(2024, 1, 1, 10, 0),
            updated_at=datetime(2024, 1, 1, 12, 0),
            reviews=[
                PRReview(
                    reviewer="reviewer1",
                    state="DISMISSED",
                    submitted_at=datetime(2024, 1, 1, 11, 0),
                ),
                PRReview(
                    reviewer="reviewer2",
                    state="APPROVED",
                    submitted_at=datetime(2024, 1, 1, 11, 30),
                ),
            ],
        )
        assert pr.has_approval is True
        assert pr.time_to_first_review == 5400  # First non-dismissed review at 11:30 (1.5 hours)
