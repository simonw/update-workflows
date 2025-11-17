#!/usr/bin/env python3
"""
CLI tool to update GitHub workflow files from remote templates.

Reads .github/workflows.yml which contains references like:
  - username/workflow-name
  - username/other-workflow

Or with custom filenames:
  test: username/workflow-name
  publish: username/other-workflow

Then fetches the latest version from:
  https://raw.githubusercontent.com/username/actions-workflows/refs/heads/main/workflow-name.yml

And replaces the local file with the fetched content.
"""

import argparse
import sys
import urllib.request
from pathlib import Path
from typing import Optional, Union
import yaml


def parse_workflows_config(config_path: Path) -> dict[str, str]:
    """
    Parse the workflows.yml config file.

    Returns a dict mapping workflow filename -> template reference (username/workflow-name).
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        if config is None:
            return {}

        # Handle list format: ['username/workflow-name', ...]
        if isinstance(config, list):
            result = {}
            for item in config:
                if isinstance(item, str) and '/' in item:
                    # Extract workflow name from reference
                    workflow_name = item.split('/')[-1]
                    result[workflow_name] = item
            return result

        # Handle dict format: {filename: 'username/workflow-name', ...}
        elif isinstance(config, dict):
            return {str(k): str(v) for k, v in config.items()}

        else:
            print(f"Warning: Unexpected config format in {config_path}", file=sys.stderr)
            return {}

    except FileNotFoundError:
        print(f"Error: Config file {config_path} not found", file=sys.stderr)
        return {}
    except yaml.YAMLError as e:
        print(f"Error parsing {config_path}: {e}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"Error reading {config_path}: {e}", file=sys.stderr)
        return {}


def build_remote_url(template_reference: str) -> str:
    """Build the raw GitHub URL for the workflow template."""
    # Parse username/workflow-name format
    if '/' not in template_reference:
        raise ValueError(f"Invalid template reference: {template_reference}")

    parts = template_reference.split('/')
    if len(parts) != 2:
        raise ValueError(f"Invalid template reference format: {template_reference}")

    username, workflow_name = parts
    return f"https://raw.githubusercontent.com/{username}/actions-workflows/refs/heads/main/{workflow_name}.yml"


def fetch_remote_content(url: str) -> Optional[str]:
    """Fetch content from a remote URL."""
    try:
        with urllib.request.urlopen(url) as response:
            return response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code} fetching {url}: {e.reason}", file=sys.stderr)
    except urllib.error.URLError as e:
        print(f"URL Error fetching {url}: {e.reason}", file=sys.stderr)
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)

    return None


def update_workflow_file(file_path: Path, template_reference: str, dry_run: bool = False) -> bool:
    """
    Update a single workflow file from a template reference.

    Returns True if the file was updated (or would be in dry-run mode).
    """
    try:
        remote_url = build_remote_url(template_reference)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return False

    print(f"Processing: {file_path.name}")
    print(f"  Template: {template_reference}")
    print(f"  Fetching from: {remote_url}")

    remote_content = fetch_remote_content(remote_url)

    if remote_content is None:
        print(f"  Failed to fetch content, skipping", file=sys.stderr)
        return False

    if dry_run:
        print(f"  [DRY RUN] Would update {file_path}")
        return True

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(remote_content)
        print(f"  Successfully updated {file_path}")
        return True
    except Exception as e:
        print(f"  Error writing to {file_path}: {e}", file=sys.stderr)
        return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Update GitHub workflow files from remote templates"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes"
    )
    parser.add_argument(
        "--workflows-dir",
        default=".github/workflows",
        help="Path to workflows directory (default: .github/workflows)"
    )

    args = parser.parse_args()

    workflows_dir = Path(args.workflows_dir)
    config_path = Path(".github/workflows.yml")

    if not workflows_dir.exists():
        print(f"Error: Directory {workflows_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    # Parse the configuration file
    workflow_configs = parse_workflows_config(config_path)

    if not workflow_configs:
        print(f"No workflows configured in {config_path}")
        sys.exit(1)

    print(f"Found {len(workflow_configs)} workflow(s) to update\n")

    updated_count = 0
    for filename, template_ref in workflow_configs.items():
        # Ensure filename ends with .yml
        if not filename.endswith('.yml') and not filename.endswith('.yaml'):
            filename = f"{filename}.yml"

        file_path = workflows_dir / filename

        if update_workflow_file(file_path, template_ref, dry_run=args.dry_run):
            updated_count += 1
        print()  # Blank line between files

    print(f"{'Would update' if args.dry_run else 'Updated'} {updated_count} file(s)")

    return 0 if updated_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
