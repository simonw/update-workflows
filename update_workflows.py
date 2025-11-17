#!/usr/bin/env python3
"""
CLI tool to update GitHub workflow files from remote templates.

Scans .github/workflows/*.yml files for comments like:
  # username/workflow-name

Then fetches the latest version from:
  https://raw.githubusercontent.com/username/actions-workflows/refs/heads/main/workflow-name.yml

And replaces the local file with the fetched content.
"""

import argparse
import glob
import re
import sys
import urllib.request
from pathlib import Path
from typing import Optional


def extract_template_reference(file_path: str) -> Optional[tuple[str, str]]:
    """
    Extract the template reference from the first line of a workflow file.

    Returns (username, workflow_name) if found, None otherwise.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()

        # Match pattern: # username/workflow-name
        match = re.match(r'^#\s*([^/\s]+)/([^/\s]+)\s*$', first_line)
        if match:
            return match.group(1), match.group(2)
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)

    return None


def build_remote_url(username: str, workflow_name: str) -> str:
    """Build the raw GitHub URL for the workflow template."""
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


def update_workflow_file(file_path: str, dry_run: bool = False) -> bool:
    """
    Update a single workflow file if it has a template reference.

    Returns True if the file was updated (or would be in dry-run mode).
    """
    template_ref = extract_template_reference(file_path)

    if not template_ref:
        return False

    username, workflow_name = template_ref
    remote_url = build_remote_url(username, workflow_name)

    print(f"Found reference: {username}/{workflow_name} in {file_path}")
    print(f"Fetching from: {remote_url}")

    remote_content = fetch_remote_content(remote_url)

    if remote_content is None:
        print(f"Failed to fetch content, skipping {file_path}", file=sys.stderr)
        return False

    if dry_run:
        print(f"[DRY RUN] Would update {file_path}")
        return True

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(remote_content)
        print(f"Successfully updated {file_path}")
        return True
    except Exception as e:
        print(f"Error writing to {file_path}: {e}", file=sys.stderr)
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

    if not workflows_dir.exists():
        print(f"Error: Directory {workflows_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    # Find all .yml and .yaml files
    workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))

    if not workflow_files:
        print(f"No workflow files found in {workflows_dir}")
        sys.exit(0)

    print(f"Scanning {len(workflow_files)} workflow file(s)...\n")

    updated_count = 0
    for workflow_file in workflow_files:
        if update_workflow_file(str(workflow_file), dry_run=args.dry_run):
            updated_count += 1
        print()  # Blank line between files

    print(f"{'Would update' if args.dry_run else 'Updated'} {updated_count} file(s)")

    return 0 if updated_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
