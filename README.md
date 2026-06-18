# PR Insights

Analyze GitHub pull request patterns and generate insights on review times, merge patterns, and contributor statistics.

## Features

- **PR Statistics**: Total PRs, merge rate, average time to merge, average time to first review
- **Contributor Analysis**: Per-author PR counts, merge rates, review participation
- **Label Tracking**: PR distribution by labels
- **Stale PR Detection**: Identify PRs that haven't been updated in a configurable number of days
- **Export Options**: Human-readable reports and JSON output

## Installation

```bash
# Using uv (recommended)
uv pip install pr-insights

# Or from source
git clone https://github.com/jlaportebot/pr-insights
cd pr-insights
uv sync --all-groups
```

## Usage

### Analyze a Repository

```bash
# Set your GitHub token
export GITHUB_TOKEN=your_token_here

# Analyze all PRs in a repository
pr-insights analyze owner repo

# Analyze only open PRs
pr-insights analyze owner repo --state open

# Save report as JSON
pr-insights analyze owner repo --output report.json

# Custom stale PR threshold (default: 30 days)
pr-insights analyze owner repo --days-stale 14
```

### View a Specific PR

```bash
pr-insights pr owner repo 42
```

### List Stale PRs

```bash
pr-insights stale owner repo --days 30
```

## Commands

| Command | Description |
|---------|-------------|
| `analyze` | Full repository PR analysis |
| `pr` | View details for a specific PR |
| `stale` | List stale PRs |

## Configuration

The tool uses a GitHub personal access token. Set it via:

- `GITHUB_TOKEN` environment variable
- `--token` / `-t` command line option

The token needs `repo` scope for private repositories.

## Development

### Setup

```bash
uv sync --all-groups
```

### Run Tests

```bash
uv run pytest
```

### Linting & Formatting

```bash
uv run ruff check .
uv run ruff format .
```

### Type Checking

```bash
uv run ty check src/
```

## Requirements

- Python 3.11+
- GitHub personal access token with `repo` scope

## License

MIT License - see LICENSE file for details.
