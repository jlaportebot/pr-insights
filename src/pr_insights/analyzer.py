"""PR analysis engine for PR Insights."""

from collections import defaultdict
from datetime import datetime, timedelta

from pr_insights.models import ContributorStat, ContributorStats, PRStats, PullRequest


class PRAnalyzer:
    """Analyzes pull request data to generate insights."""

    def __init__(self, prs: list[PullRequest]):
        self.prs = prs

    def get_stats(self) -> PRStats:
        """Get aggregated PR statistics."""
        return PRStats(prs=self.prs)

    def get_contributor_stats(self) -> ContributorStats:
        """Get contributor statistics."""
        return ContributorStats.from_prs(self.prs)

    def get_top_contributors(self, limit: int = 10) -> list[tuple[str, "ContributorStat"]]:
        """Get top contributors by PR count."""
        stats = self.get_contributor_stats()
        sorted_contributors = sorted(
            stats.contributors.items(),
            key=lambda x: x[1].total_prs,
            reverse=True,
        )
        return sorted_contributors[:limit]

    def get_prs_by_label(self) -> dict[str, list[PullRequest]]:
        """Group PRs by label."""
        by_label: dict[str, list[PullRequest]] = defaultdict(list)
        for pr in self.prs:
            for label in pr.labels:
                by_label[label].append(pr)
        return dict(by_label)

    def get_prs_by_author(self) -> dict[str, list[PullRequest]]:
        """Group PRs by author."""
        by_author: dict[str, list[PullRequest]] = defaultdict(list)
        for pr in self.prs:
            by_author[pr.author].append(pr)
        return dict(by_author)

    def get_merge_rate_by_author(self) -> dict[str, float]:
        """Calculate merge rate per author."""
        by_author = self.get_prs_by_author()
        rates = {}
        for author, prs in by_author.items():
            merged = sum(1 for pr in prs if pr.is_merged)
            rates[author] = merged / len(prs) if prs else 0.0
        return rates

    def get_avg_pr_size(self) -> dict[str, float]:
        """Calculate average PR size metrics."""
        if not self.prs:
            return {"avg_additions": 0.0, "avg_deletions": 0.0, "avg_changed_files": 0.0}

        total_additions = sum(pr.additions for pr in self.prs)
        total_deletions = sum(pr.deletions for pr in self.prs)
        total_files = sum(pr.changed_files for pr in self.prs)
        count = len(self.prs)

        return {
            "avg_additions": total_additions / count,
            "avg_deletions": total_deletions / count,
            "avg_changed_files": total_files / count,
        }

    def get_review_participation(self) -> dict[str, int]:
        """Get review participation count per reviewer."""
        participation: dict[str, int] = defaultdict(int)
        for pr in self.prs:
            for review in pr.reviews:
                participation[review.reviewer] += 1
        return dict(participation)

    def get_stale_prs(
        self, days: int = 30, reference_time: datetime | None = None
    ) -> list[PullRequest]:
        """Get open PRs that haven't been updated in the specified number of days."""
        if reference_time is None:
            reference_time = datetime.now()

        cutoff = reference_time - timedelta(days=days)
        stale = [pr for pr in self.prs if pr.is_open and pr.updated_at < cutoff]
        return sorted(stale, key=lambda pr: pr.updated_at)

    def generate_report(self) -> str:
        """Generate a human-readable report."""
        stats = self.get_stats()
        contrib_stats = self.get_contributor_stats()
        by_label = self.get_prs_by_label()
        avg_size = self.get_avg_pr_size()
        merge_rates = self.get_merge_rate_by_author()

        lines = [
            "=" * 50,
            "PR Insights Report",
            "=" * 50,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "Summary:",
            f"  Total PRs: {stats.total_prs}",
            f"  Merged: {stats.merged_prs}",
            f"  Open: {stats.open_prs}",
            f"  Closed (unmerged): {stats.closed_prs - stats.merged_prs}",
            f"  Merge Rate: {stats.merge_rate * 100:.1f}%",
            "",
        ]

        if stats.avg_time_to_merge:
            avg_hours = stats.avg_time_to_merge / 3600
            lines.append(f"  Avg Time to Merge: {avg_hours:.1f} hours")

        if stats.avg_time_to_first_review:
            avg_hours = stats.avg_time_to_first_review / 3600
            lines.append(f"  Avg Time to First Review: {avg_hours:.1f} hours")

        lines.extend(
            [
                "",
                "PR Size (avg):",
                f"  Additions: {avg_size['avg_additions']:.0f}",
                f"  Deletions: {avg_size['avg_deletions']:.0f}",
                f"  Changed Files: {avg_size['avg_changed_files']:.1f}",
                "",
                "By Label:",
            ]
        )

        for label, prs in sorted(by_label.items(), key=lambda x: len(x[1]), reverse=True):
            merged = sum(1 for pr in prs if pr.is_merged)
            lines.append(f"  {label}: {len(prs)} PRs ({merged} merged)")

        lines.extend(
            [
                "",
                "Contributors:",
            ]
        )

        for login, stat in sorted(
            contrib_stats.contributors.items(), key=lambda x: x[1].total_prs, reverse=True
        ):
            lines.append(
                f"  {login}: {stat.total_prs} PRs "
                f"({stat.merged_prs} merged, {stat.open_prs} open, "
                f"merge rate: {stat.merge_rate * 100:.0f}%)"
            )

        lines.extend(
            [
                "",
                "Merge Rate by Author:",
            ]
        )

        for author, rate in sorted(merge_rates.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {author}: {rate * 100:.0f}%")

        return "\n".join(lines)

    def export_to_dict(self) -> dict:
        """Export analysis results to a dictionary."""
        stats = self.get_stats()
        contrib_stats = self.get_contributor_stats()
        by_label = self.get_prs_by_label()
        by_author = self.get_prs_by_author()
        merge_rates = self.get_merge_rate_by_author()
        avg_size = self.get_avg_pr_size()
        review_participation = self.get_review_participation()

        return {
            "summary": {
                "total_prs": stats.total_prs,
                "merged_prs": stats.merged_prs,
                "open_prs": stats.open_prs,
                "closed_prs": stats.closed_prs,
                "merge_rate": stats.merge_rate,
                "avg_time_to_merge_hours": stats.avg_time_to_merge / 3600
                if stats.avg_time_to_merge
                else None,
                "avg_time_to_first_review_hours": stats.avg_time_to_first_review / 3600
                if stats.avg_time_to_first_review
                else None,
            },
            "contributors": {
                login: {
                    "total_prs": stat.total_prs,
                    "merged_prs": stat.merged_prs,
                    "open_prs": stat.open_prs,
                    "closed_prs": stat.closed_prs,
                    "merge_rate": stat.merge_rate,
                    "total_additions": stat.total_additions,
                    "total_deletions": stat.total_deletions,
                }
                for login, stat in contrib_stats.contributors.items()
            },
            "labels": {label: len(prs) for label, prs in by_label.items()},
            "by_author": {author: len(prs) for author, prs in by_author.items()},
            "merge_rate_by_author": merge_rates,
            "avg_pr_size": avg_size,
            "review_participation": review_participation,
        }
