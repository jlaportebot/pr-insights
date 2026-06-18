"""CLI for PR Insights."""

import sys
from datetime import datetime

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from pr_insights.analyzer import PRAnalyzer
from pr_insights.github_client import GitHubClient

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="pr-insights")
def cli():
    """Analyze GitHub pull request patterns and generate insights."""


@cli.command()
@click.argument("owner")
@click.argument("repo")
@click.option("--token", "-t", envvar="GITHUB_TOKEN", help="GitHub personal access token")
@click.option(
    "--state",
    "-s",
    default="all",
    type=click.Choice(["open", "closed", "all"]),
    help="PR state to fetch",
)
@click.option(
    "--max-pages", "-p", default=None, type=int, help="Maximum pages to fetch (100 PRs per page)"
)
@click.option("--output", "-o", type=click.Path(), help="Output file for report (JSON)")
@click.option("--days-stale", default=30, type=int, help="Days threshold for stale PR detection")
def analyze(
    owner: str,
    repo: str,
    token: str | None,
    state: str,
    max_pages: int | None,
    output: str | None,
    days_stale: int,
):
    """Analyze PRs for a repository."""
    if not token:
        console.print(
            "[red]Error: GitHub token required. Set GITHUB_TOKEN env var or use --token.[/red]"
        )
        sys.exit(1)

    async def run_analysis():
        client = GitHubClient(token=token)
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(f"Fetching PRs from {owner}/{repo}...", total=None)
                prs = await client.get_prs(owner, repo, state=state, max_pages=max_pages)
                progress.update(task, description=f"Analyzing {len(prs)} PRs...")

            analyzer = PRAnalyzer(prs)

            # Generate text report
            report_text = analyzer.generate_report()
            console.print(report_text)

            # Export data for additional displays
            report_data = analyzer.export_to_dict()

            # Stale PRs
            stale_prs = analyzer.get_stale_prs(days=days_stale)
            if stale_prs:
                stale_table = Table(title=f"Stale PRs (>{days_stale} days since update)")
                stale_table.add_column("#", justify="right")
                stale_table.add_column("Title", style="cyan")
                stale_table.add_column("Author", style="green")
                stale_table.add_column("Days Since Update", justify="right")
                stale_table.add_column("Labels", style="dim")
                for pr in stale_prs[:10]:
                    days = (datetime.now() - pr.updated_at).days
                    stale_table.add_row(
                        str(pr.number),
                        pr.title[:60],
                        pr.author,
                        str(days),
                        ", ".join(pr.labels[:3]) + ("..." if len(pr.labels) > 3 else ""),
                    )
                console.print(stale_table)

            if output:
                import json

                with open(output, "w") as f:
                    json.dump(report_data, f, indent=2, default=str)
                console.print(f"[green]Report saved to {output}[/green]")

        finally:
            await client.close()

    import asyncio

    asyncio.run(run_analysis())


@cli.command()
@click.argument("owner")
@click.argument("repo")
@click.argument("pr_number", type=int)
@click.option("--token", "-t", envvar="GITHUB_TOKEN", help="GitHub personal access token")
def pr(owner: str, repo: str, pr_number: int, token: str | None):
    """Get details for a specific PR."""
    if not token:
        console.print(
            "[red]Error: GitHub token required. Set GITHUB_TOKEN env var or use --token.[/red]"
        )
        sys.exit(1)

    async def run():
        client = GitHubClient(token=token)
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(f"Fetching PR #{pr_number}...", total=None)
                pr = await client.get_pr(owner, repo, pr_number)

            console.print(
                Panel.fit(
                    f"[bold]#{pr.number}: {pr.title}[/bold]\n"
                    f"State: {pr.state.value}\n"
                    f"Author: {pr.author}\n"
                    f"Created: {pr.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                    f"Updated: {pr.updated_at.strftime('%Y-%m-%d %H:%M')}\n"
                    f"Merged: {'Yes' if pr.is_merged else 'No'}"
                    + (
                        f" (by {pr.merged_by} at {pr.merged_at.strftime('%Y-%m-%d %H:%M')})"
                        if pr.merged_at
                        else ""
                    )
                    + "\n"
                    f"Labels: {', '.join(pr.labels) if pr.labels else 'None'}\n"
                    f"Additions: {pr.additions}, Deletions: {pr.deletions}, Files: {pr.changed_files}\n"
                    f"Reviews: {len(pr.reviews)} ({sum(1 for r in pr.reviews if r.state.value == 'APPROVED')} approved, {sum(1 for r in pr.reviews if r.state.value == 'CHANGES_REQUESTED')} changes requested)\n"
                    f"Commits: {len(pr.commits)}",
                    title=f"PR #{pr.number}",
                    border_style="blue",
                )
            )

            if pr.reviews:
                review_table = Table(title="Reviews")
                review_table.add_column("Reviewer", style="cyan")
                review_table.add_column("State", style="green")
                review_table.add_column("Submitted", style="yellow")
                review_table.add_column("Comment", style="dim")
                for review in pr.reviews:
                    review_table.add_row(
                        review.reviewer,
                        review.state.value,
                        review.submitted_at.strftime("%Y-%m-%d %H:%M"),
                        (review.body or "")[:80]
                        + ("..." if review.body and len(review.body) > 80 else ""),
                    )
                console.print(review_table)

        finally:
            await client.close()

    import asyncio

    asyncio.run(run())


@cli.command()
@click.argument("owner")
@click.argument("repo")
@click.option("--token", "-t", envvar="GITHUB_TOKEN", help="GitHub personal access token")
@click.option("--days", "-d", default=30, type=int, help="Days threshold for stale PRs")
def stale(owner: str, repo: str, token: str | None, days: int):
    """List stale PRs in a repository."""
    if not token:
        console.print(
            "[red]Error: GitHub token required. Set GITHUB_TOKEN env var or use --token.[/red]"
        )
        sys.exit(1)

    async def run():
        client = GitHubClient(token=token)
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(f"Fetching PRs from {owner}/{repo}...", total=None)
                prs = await client.get_prs(owner, repo, state="open")
                progress.update(task, description=f"Analyzing {len(prs)} open PRs...")

            analyzer = PRAnalyzer(prs)
            stale_prs = analyzer.get_stale_prs(days=days)

            if stale_prs:
                table = Table(title=f"Stale PRs (>{days} days since update)")
                table.add_column("#", justify="right")
                table.add_column("Title", style="cyan")
                table.add_column("Author", style="green")
                table.add_column("Days Since Update", justify="right")
                table.add_column("Labels", style="dim")
                for pr in stale_prs:
                    days_open = (datetime.now() - pr.updated_at).days
                    table.add_row(
                        str(pr.number),
                        pr.title[:60],
                        pr.author,
                        str(days_open),
                        ", ".join(pr.labels[:3]) + ("..." if len(pr.labels) > 3 else ""),
                    )
                console.print(table)
            else:
                console.print(f"[green]No stale PRs found (threshold: {days} days)[/green]")

        finally:
            await client.close()

    import asyncio

    asyncio.run(run())


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
