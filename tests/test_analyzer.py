"""Tests for PR analyzer."""

from datetime import datetime, timedelta

import pytest

from pr_insights.analyzer import PRAnalyzer
from pr_insights.models import (
    PRReview,
    PRState,
    PullRequest,
    ReviewState,
)


class TestPRAnalyzer:
    """Tests for PRAnalyzer."""

    @pytest.fixture
    def sample_prs(self):
        """Create sample PRs for testing."""
        now = datetime(2024, 6, 15, 12, 0, 0)
        return [
            PullRequest(
                number=1,
                title="Fix authentication bug",
                state=PRState.CLOSED,
                author="alice",
                created_at=now - timedelta(days=10),
                updated_at=now - timedelta(days=9),
                merged_at=now - timedelta(days=9),
                merged_by="bob",
                labels=["bug", "backend"],
                reviews=[
                    PRReview(
                        reviewer="bob",
                        state=ReviewState.APPROVED,
                        submitted_at=now - timedelta(days=9, hours=23),
                    ),
                ],
                additions=50,
                deletions=20,
                changed_files=3,
            ),
            PullRequest(
                number=2,
                title="Add new feature",
                state=PRState.OPEN,
                author="bob",
                created_at=now - timedelta(days=5),
                updated_at=now - timedelta(days=4),
                labels=["feature", "frontend"],
                reviews=[
                    PRReview(
                        reviewer="alice",
                        state=ReviewState.CHANGES_REQUESTED,
                        submitted_at=now - timedelta(days=4, hours=23),
                    ),
                    PRReview(
                        reviewer="charlie",
                        state=ReviewState.APPROVED,
                        submitted_at=now - timedelta(days=4, hours=22),
                    ),
                ],
                additions=200,
                deletions=50,
                changed_files=10,
            ),
            PullRequest(
                number=3,
                title="Update documentation",
                state=PRState.CLOSED,
                author="alice",
                created_at=now - timedelta(days=20),
                updated_at=now - timedelta(days=19),
                merged_at=None,  # closed without merge
                labels=["docs"],
                reviews=[],
                additions=10,
                deletions=5,
                changed_files=2,
            ),
            PullRequest(
                number=4,
                title="Refactor API",
                state=PRState.CLOSED,
                author="charlie",
                created_at=now - timedelta(days=15),
                updated_at=now - timedelta(days=14),
                merged_at=now - timedelta(days=14),
                merged_by="alice",
                labels=["refactor", "backend"],
                reviews=[
                    PRReview(
                        reviewer="alice",
                        state=ReviewState.APPROVED,
                        submitted_at=now - timedelta(days=14, hours=23),
                    ),
                    PRReview(
                        reviewer="bob",
                        state=ReviewState.APPROVED,
                        submitted_at=now - timedelta(days=14, hours=22),
                    ),
                ],
                additions=300,
                deletions=150,
                changed_files=15,
            ),
        ]

    def test_analyze_basic_stats(self, sample_prs):
        """Test basic statistics calculation."""
        analyzer = PRAnalyzer(sample_prs)
        stats = analyzer.get_stats()

        assert stats.total_prs == 4
        assert stats.merged_prs == 2
        assert stats.open_prs == 1
        assert stats.closed_prs == 3
        assert stats.merge_rate == 0.5

    def test_analyze_time_to_merge(self, sample_prs):
        """Test average time to merge calculation."""
        analyzer = PRAnalyzer(sample_prs)
        stats = analyzer.get_stats()

        # PR 1: 1 day, PR 4: 1 day -> avg 1 day = 86400 seconds
        assert stats.avg_time_to_merge is not None
        assert abs(stats.avg_time_to_merge - 86400) < 1

    def test_analyze_time_to_first_review(self, sample_prs):
        """Test average time to first review."""
        analyzer = PRAnalyzer(sample_prs)
        stats = analyzer.get_stats()

        # PR 1: 1 hour, PR 2: 1 hour, PR 4: 1 hour -> avg 1 hour = 3600 seconds
        # PR 3 has no reviews
        assert stats.avg_time_to_first_review is not None
        assert abs(stats.avg_time_to_first_review - 3600) < 1

    def test_contributor_stats(self, sample_prs):
        """Test contributor statistics."""
        analyzer = PRAnalyzer(sample_prs)
        contrib_stats = analyzer.get_contributor_stats()

        assert len(contrib_stats.contributors) == 3
        assert contrib_stats.contributors["alice"].total_prs == 2
        assert contrib_stats.contributors["alice"].merged_prs == 1
        assert contrib_stats.contributors["bob"].total_prs == 1
        assert contrib_stats.contributors["bob"].open_prs == 1
        assert contrib_stats.contributors["charlie"].total_prs == 1
        assert contrib_stats.contributors["charlie"].merged_prs == 1

    def test_top_contributors(self, sample_prs):
        """Test getting top contributors by PR count."""
        analyzer = PRAnalyzer(sample_prs)
        top = analyzer.get_top_contributors(limit=2)

        assert len(top) == 2
        assert top[0][0] == "alice"
        assert top[0][1].total_prs == 2

    def test_prs_by_label(self, sample_prs):
        """Test grouping PRs by label."""
        analyzer = PRAnalyzer(sample_prs)
        by_label = analyzer.get_prs_by_label()

        assert "bug" in by_label
        assert "backend" in by_label
        assert "feature" in by_label
        assert "frontend" in by_label
        assert "docs" in by_label
        assert "refactor" in by_label
        assert len(by_label["bug"]) == 1
        assert len(by_label["backend"]) == 2

    def test_prs_by_author(self, sample_prs):
        """Test grouping PRs by author."""
        analyzer = PRAnalyzer(sample_prs)
        by_author = analyzer.get_prs_by_author()

        assert len(by_author["alice"]) == 2
        assert len(by_author["bob"]) == 1
        assert len(by_author["charlie"]) == 1

    def test_merge_rate_by_author(self, sample_prs):
        """Test merge rate calculation per author."""
        analyzer = PRAnalyzer(sample_prs)
        rates = analyzer.get_merge_rate_by_author()

        assert rates["alice"] == 0.5  # 1 merged out of 2
        assert rates["bob"] == 0.0  # 0 merged out of 1 (open)
        assert rates["charlie"] == 1.0  # 1 merged out of 1

    def test_avg_pr_size(self, sample_prs):
        """Test average PR size calculation."""
        analyzer = PRAnalyzer(sample_prs)
        size = analyzer.get_avg_pr_size()

        # (50+200+10+300) / 4 = 140 additions
        # (20+50+5+150) / 4 = 56.25 deletions
        assert size["avg_additions"] == 140
        assert size["avg_deletions"] == 56.25
        assert size["avg_changed_files"] == 7.5

    def test_review_participation(self, sample_prs):
        """Test reviewer participation stats."""
        analyzer = PRAnalyzer(sample_prs)
        participation = analyzer.get_review_participation()

        # alice reviewed PR 2 (changes) and PR 4 (approved)
        # bob reviewed PR 1 (approved) and PR 4 (approved)
        # charlie reviewed PR 2 (approved)
        assert participation["alice"] == 2
        assert participation["bob"] == 2
        assert participation["charlie"] == 1

    def test_stale_prs(self, sample_prs):
        """Test identifying stale PRs."""
        analyzer = PRAnalyzer(sample_prs)
        # Use fixed reference time matching the fixture
        reference_time = datetime(2024, 6, 15, 12, 0, 0)
        stale = analyzer.get_stale_prs(days=7, reference_time=reference_time)

        # PR 1: updated 9 days ago (merged, not stale)
        # PR 2: updated 4 days ago (open, not stale)
        # PR 3: updated 19 days ago (closed, not stale)
        # PR 4: updated 14 days ago (merged, not stale)
        # Should only return open PRs older than threshold
        assert len(stale) == 0  # No open PRs older than 7 days

        # Test with 3 days threshold
        stale = analyzer.get_stale_prs(days=3, reference_time=reference_time)
        assert len(stale) == 1
        assert stale[0].number == 2

    def test_empty_analyzer(self):
        """Test analyzer with no PRs."""
        analyzer = PRAnalyzer([])
        stats = analyzer.get_stats()

        assert stats.total_prs == 0
        assert stats.merged_prs == 0
        assert stats.merge_rate == 0.0
        assert stats.avg_time_to_merge is None
        assert stats.avg_time_to_first_review is None

        contrib = analyzer.get_contributor_stats()
        assert len(contrib.contributors) == 0

    def test_single_pr_analyzer(self):
        """Test analyzer with single PR."""
        pr = PullRequest(
            number=1,
            title="Test",
            state=PRState.OPEN,
            author="author",
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
        )
        analyzer = PRAnalyzer([pr])
        stats = analyzer.get_stats()

        assert stats.total_prs == 1
        assert stats.open_prs == 1
        assert stats.merged_prs == 0

    def test_generate_report(self, sample_prs):
        """Test report generation."""
        analyzer = PRAnalyzer(sample_prs)
        report = analyzer.generate_report()

        assert "PR Insights Report" in report
        assert "Total PRs: 4" in report
        assert "Merged: 2" in report
        assert "Open: 1" in report
        assert "Merge Rate: 50.0%" in report
        assert "alice" in report
        assert "bob" in report
        assert "charlie" in report

    def test_export_to_dict(self, sample_prs):
        """Test exporting analysis to dictionary."""
        analyzer = PRAnalyzer(sample_prs)
        data = analyzer.export_to_dict()

        assert data["summary"]["total_prs"] == 4
        assert data["summary"]["merged_prs"] == 2
        assert "contributors" in data
        assert "labels" in data
        assert "by_author" in data
