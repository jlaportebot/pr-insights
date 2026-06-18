"""Tests for CLI."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from pr_insights.cli import cli


class TestCLI:
    """Tests for CLI commands."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_client(self):
        """Create a mock GitHub client."""
        with patch("pr_insights.cli.GitHubClient") as mock:
            client = MagicMock()
            client.get_prs = AsyncMock()
            client.get_pr = AsyncMock()
            client.close = AsyncMock()
            mock.return_value = client
            yield client

    def test_cli_help(self, runner):
        """Test CLI help command."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Analyze GitHub pull request patterns" in result.output

    def test_analyze_help(self, runner):
        """Test analyze command help."""
        result = runner.invoke(cli, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "Analyze PRs for a repository" in result.output

    def test_pr_help(self, runner):
        """Test pr command help."""
        result = runner.invoke(cli, ["pr", "--help"])
        assert result.exit_code == 0
        assert "Get details for a specific PR" in result.output

    def test_stale_help(self, runner):
        """Test stale command help."""
        result = runner.invoke(cli, ["stale", "--help"])
        assert result.exit_code == 0
        assert "List stale PRs in a repository" in result.output

    def test_analyze_requires_token(self, runner):
        """Test analyze command requires token."""
        result = runner.invoke(cli, ["analyze", "owner", "repo"], env={})
        assert result.exit_code != 0
        assert "GitHub token required" in result.output

    def test_analyze_with_token(self, runner, mock_client):
        """Test analyze command with token."""
        # Setup mock PRs
        from pr_insights.models import PRState, PullRequest

        mock_prs = [
            PullRequest(
                number=1,
                title="Test PR",
                state=PRState.OPEN,
                author="author",
                created_at=datetime(2024, 1, 1),
                updated_at=datetime(2024, 1, 1),
            )
        ]
        mock_client.get_prs.return_value = mock_prs

        result = runner.invoke(cli, ["analyze", "owner", "repo", "--token", "test-token"])
        assert result.exit_code == 0
        mock_client.get_prs.assert_called_once()

    def test_pr_requires_token(self, runner):
        """Test pr command requires token."""
        result = runner.invoke(cli, ["pr", "owner", "repo", "1"], env={})
        assert result.exit_code != 0
        assert "GitHub token required" in result.output

    def test_stale_requires_token(self, runner):
        """Test stale command requires token."""
        result = runner.invoke(cli, ["stale", "owner", "repo"], env={})
        assert result.exit_code != 0
        assert "GitHub token required" in result.output

    def test_version(self, runner):
        """Test version option."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output
