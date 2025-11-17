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
import subprocess
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
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if config is None:
            return {}

        # Handle list format: ['username/workflow-name', ...]
        if isinstance(config, list):
            result = {}
            for item in config:
                if isinstance(item, str) and "/" in item:
                    # Extract workflow name from reference
                    workflow_name = item.split("/")[-1]
                    result[workflow_name] = item
            return result

        # Handle dict format: {filename: 'username/workflow-name', ...}
        elif isinstance(config, dict):
            return {str(k): str(v) for k, v in config.items()}

        else:
            print(
                f"Warning: Unexpected config format in {config_path}", file=sys.stderr
            )
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
    if "/" not in template_reference:
        raise ValueError(f"Invalid template reference: {template_reference}")

    parts = template_reference.split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid template reference format: {template_reference}")

    username, workflow_name = parts
    return f"https://raw.githubusercontent.com/{username}/actions-workflows/refs/heads/main/{workflow_name}.yml"


def fetch_remote_content(url: str) -> Optional[str]:
    """Fetch content from a remote URL."""
    try:
        with urllib.request.urlopen(url) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code} fetching {url}: {e.reason}", file=sys.stderr)
    except urllib.error.URLError as e:
        print(f"URL Error fetching {url}: {e.reason}", file=sys.stderr)
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)

    return None


def update_workflow_file(
    file_path: Path, template_reference: str, dry_run: bool = False
) -> bool:
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

    # Check if file exists and compare content
    existing_content = None
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                existing_content = f.read()
        except Exception as e:
            print(f"  Warning: Could not read existing file: {e}", file=sys.stderr)

    if existing_content == remote_content:
        print(f"  Already up to date")
        return False

    if dry_run:
        print(f"  [DRY RUN] Would update {file_path}")
        return True

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(remote_content)
        print(f"  Successfully updated {file_path}")
        return True
    except Exception as e:
        print(f"  Error writing to {file_path}: {e}", file=sys.stderr)
        return False


def find_projects_with_config(base_dir: Path) -> list[Path]:
    """
    Find all directories containing .github/workflows.yml files.

    Returns list of project root directories (parent of .github).
    """
    projects = []
    for config_file in base_dir.rglob(".github/workflows.yml"):
        project_dir = (
            config_file.parent.parent
        )  # Go up from .github/workflows.yml to project root
        projects.append(project_dir)
    return sorted(projects)


def process_project(project_dir: Path, dry_run: bool = False) -> tuple[int, list[str]]:
    """
    Process a single project directory.

    Returns (updated_count, list of updated filenames).
    """
    workflows_dir = project_dir / ".github" / "workflows"
    config_path = project_dir / ".github" / "workflows.yml"

    if not workflows_dir.exists():
        print(f"Error: Directory {workflows_dir} does not exist", file=sys.stderr)
        return 0, []

    # Parse the configuration file
    workflow_configs = parse_workflows_config(config_path)

    if not workflow_configs:
        print(f"No workflows configured in {config_path}")
        return 0, []

    print(f"Found {len(workflow_configs)} workflow(s) to update\n")

    updated_count = 0
    updated_files = []
    for filename, template_ref in workflow_configs.items():
        # Ensure filename ends with .yml
        if not filename.endswith(".yml") and not filename.endswith(".yaml"):
            filename = f"{filename}.yml"

        file_path = workflows_dir / filename

        if update_workflow_file(file_path, template_ref, dry_run=dry_run):
            updated_count += 1
            updated_files.append(filename)
        print()  # Blank line between files

    return updated_count, updated_files


def commit_changes(
    project_dir: Path, updated_files: list[str], push: bool = False
) -> bool:
    """
    Commit the updated workflow files using git.

    Returns True if successful.
    """
    if not updated_files:
        return False

    try:
        # Check if we're in a git repository
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  Warning: {project_dir} is not a git repository", file=sys.stderr)
            return False

        # Add the updated files
        for filename in updated_files:
            file_path = project_dir / ".github" / "workflows" / filename
            subprocess.run(["git", "add", str(file_path)], cwd=project_dir, check=True)

        # Create commit message
        files_list = ", ".join(updated_files)
        commit_message = f"update-workflows: {files_list}"

        # Commit
        subprocess.run(
            ["git", "commit", "-m", commit_message], cwd=project_dir, check=True
        )
        print(f"  Committed: {commit_message}")

        # Push if requested
        if push:
            subprocess.run(["git", "push"], cwd=project_dir, check=True)
            print(f"  Pushed to remote")

        return True

    except subprocess.CalledProcessError as e:
        print(f"  Error running git: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)
        return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Update GitHub workflow files from remote templates"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Find and process all projects with .github/workflows.yml in current directory and subdirectories",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Commit changes with auto-generated message",
    )
    parser.add_argument(
        "--push", action="store_true", help="Push committed changes (implies --commit)"
    )

    args = parser.parse_args()

    # --push implies --commit
    if args.push:
        args.commit = True

    # Can't commit in dry-run mode
    if args.dry_run and (args.commit or args.push):
        print("Error: Cannot use --commit or --push with --dry-run", file=sys.stderr)
        sys.exit(1)

    if args.all:
        # Find all projects with .github/workflows.yml
        base_dir = Path.cwd()
        projects = find_projects_with_config(base_dir)

        if not projects:
            print("No projects with .github/workflows.yml found")
            sys.exit(1)

        print(f"Found {len(projects)} project(s) with workflow configs\n")

        total_updated = 0
        for project_dir in projects:
            print(f"=== Processing: {project_dir.name} ===")
            print(f"Path: {project_dir}\n")

            updated_count, updated_files = process_project(
                project_dir, dry_run=args.dry_run
            )

            if updated_count > 0:
                print(
                    f"{'Would update' if args.dry_run else 'Updated'} {updated_count} file(s) in {project_dir.name}"
                )
                total_updated += updated_count

                # Commit if requested
                if args.commit and not args.dry_run:
                    commit_changes(project_dir, updated_files, push=args.push)
            else:
                print(f"No files to update in {project_dir.name}")

            print("\n" + "=" * 60 + "\n")

        print(
            f"Total: {'Would update' if args.dry_run else 'Updated'} {total_updated} file(s) across {len(projects)} project(s)"
        )
        return 0 if total_updated > 0 else 1

    else:
        # Process single project (current directory)
        project_dir = Path.cwd()
        workflows_dir = project_dir / ".github" / "workflows"
        config_path = Path(".github/workflows.yml")

        if not workflows_dir.exists():
            print(f"Error: Directory {workflows_dir} does not exist", file=sys.stderr)
            sys.exit(1)

        # Check if config exists
        workflow_configs = parse_workflows_config(config_path)
        if not workflow_configs:
            print(f"No workflows configured in {config_path}")
            sys.exit(1)

        updated_count, updated_files = process_project(
            project_dir, dry_run=args.dry_run
        )

        print(
            f"{'Would update' if args.dry_run else 'Updated'} {updated_count} file(s)"
        )

        # Commit if requested
        if args.commit and not args.dry_run and updated_count > 0:
            commit_changes(project_dir, updated_files, push=args.push)

        return 0 if updated_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
