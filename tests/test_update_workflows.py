"""Simple CLI tests for update_workflows."""

import pytest
from pathlib import Path
from update_workflows import main
import sys
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_fetch():
    """Mock HTTP fetching to return fake workflow content."""

    def _mock_fetch(url):
        # Return different content based on the workflow name
        if "python-test" in url:
            return "name: Test\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest"
        elif "python-publish" in url:
            return (
                "name: Publish\non: push\njobs:\n  publish:\n    runs-on: ubuntu-latest"
            )
        else:
            return "name: Generic\non: push"

    with patch("update_workflows.fetch_remote_content", side_effect=_mock_fetch):
        yield _mock_fetch


@pytest.fixture
def mock_git():
    """Mock git subprocess calls."""
    with patch("subprocess.run") as mock_run:
        # Default: git repo exists and commands succeed
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield mock_run


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    """Create a temporary workspace with workflows directory."""
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)

    # Change to temp directory
    monkeypatch.chdir(tmp_path)

    return tmp_path


@pytest.fixture
def multi_project_workspace(tmp_path, monkeypatch):
    """Create multiple projects with workflow configs."""
    # Project 1
    project1 = tmp_path / "project1"
    (project1 / ".github" / "workflows").mkdir(parents=True)
    (project1 / ".github" / "workflows.yml").write_text("test: simonw/python-test\n")

    # Project 2
    project2 = tmp_path / "project2"
    (project2 / ".github" / "workflows").mkdir(parents=True)
    (project2 / ".github" / "workflows.yml").write_text(
        "publish: simonw/python-publish\n"
    )

    # Project 3 (nested)
    project3 = tmp_path / "nested" / "project3"
    (project3 / ".github" / "workflows").mkdir(parents=True)
    (project3 / ".github" / "workflows.yml").write_text(
        """- simonw/python-test
- simonw/python-publish
"""
    )

    # Project 4 (no workflows.yml - should be ignored)
    project4 = tmp_path / "project4"
    (project4 / ".github" / "workflows").mkdir(parents=True)

    # Change to base directory
    monkeypatch.chdir(tmp_path)

    return tmp_path


@pytest.mark.parametrize(
    "config_content,expected_count",
    [
        # List format
        (
            """- simonw/python-test
- simonw/python-publish
""",
            2,
        ),
        # Dict format with custom filenames
        (
            """test: simonw/python-test
publish: simonw/python-publish
""",
            2,
        ),
        # Single item list
        (
            """- simonw/python-test
""",
            1,
        ),
    ],
)
def test_dry_run_with_different_config_formats(
    temp_workspace, mock_fetch, capsys, monkeypatch, config_content, expected_count
):
    """Test dry-run with different YAML config formats."""
    # Create config file
    config_file = temp_workspace / ".github" / "workflows.yml"
    config_file.write_text(config_content)

    # Mock sys.argv for argparse
    monkeypatch.setattr(sys, "argv", ["update_workflows", "--dry-run"])

    # Run the command
    exit_code = main()

    # Check output
    captured = capsys.readouterr()
    assert "[DRY RUN]" in captured.out
    assert f"Would update {expected_count} file(s)" in captured.out
    assert exit_code == 0


def test_missing_config_file(temp_workspace, capsys, monkeypatch):
    """Test behavior when config file doesn't exist."""
    # Mock sys.argv
    monkeypatch.setattr(sys, "argv", ["update_workflows"])

    # Run without creating config file
    with pytest.raises(SystemExit) as exc_info:
        main()

    # Should exit with error
    captured = capsys.readouterr()
    assert "not found" in captured.err
    assert exc_info.value.code == 1


def test_empty_config_file(temp_workspace, capsys, monkeypatch):
    """Test behavior with empty config file."""
    # Create empty config
    config_file = temp_workspace / ".github" / "workflows.yml"
    config_file.write_text("")

    # Mock sys.argv
    monkeypatch.setattr(sys, "argv", ["update_workflows"])

    # Run the command
    with pytest.raises(SystemExit) as exc_info:
        main()

    # Should exit with error
    captured = capsys.readouterr()
    assert "No workflows configured" in captured.out
    assert exc_info.value.code == 1


def test_invalid_yaml_config(temp_workspace, capsys, monkeypatch):
    """Test behavior with invalid YAML."""
    # Create invalid YAML config
    config_file = temp_workspace / ".github" / "workflows.yml"
    config_file.write_text("invalid: yaml: content:\n  - bad: indentation")

    # Mock sys.argv
    monkeypatch.setattr(sys, "argv", ["update_workflows"])

    # Run the command
    with pytest.raises(SystemExit) as exc_info:
        main()

    # Should handle error gracefully
    captured = capsys.readouterr()
    assert "Error parsing" in captured.err or "No workflows configured" in captured.out
    assert exc_info.value.code == 1


def test_missing_workflows_directory(temp_workspace, capsys, monkeypatch):
    """Test behavior when workflows directory doesn't exist."""
    # Remove workflows directory
    import shutil

    shutil.rmtree(temp_workspace / ".github" / "workflows")

    # Mock sys.argv
    monkeypatch.setattr(sys, "argv", ["update_workflows"])

    # Run the command
    with pytest.raises(SystemExit) as exc_info:
        main()

    # Should exit with error
    captured = capsys.readouterr()
    assert "does not exist" in captured.err
    assert exc_info.value.code == 1


# Tests for --all option


def test_all_finds_multiple_projects(
    multi_project_workspace, mock_fetch, capsys, monkeypatch
):
    """Test --all finds and processes multiple projects."""
    monkeypatch.setattr(sys, "argv", ["update_workflows", "--all", "--dry-run"])

    exit_code = main()

    captured = capsys.readouterr()
    assert "Found 3 project(s)" in captured.out
    assert "project1" in captured.out
    assert "project2" in captured.out
    assert "project3" in captured.out
    assert "project4" not in captured.out  # No workflows.yml
    assert exit_code == 0


def test_all_processes_nested_projects(
    multi_project_workspace, mock_fetch, capsys, monkeypatch
):
    """Test --all finds projects in nested directories."""
    monkeypatch.setattr(sys, "argv", ["update_workflows", "--all", "--dry-run"])

    exit_code = main()

    captured = capsys.readouterr()
    assert "project3" in captured.out  # Nested project
    assert "nested/project3" in captured.out or "project3" in captured.out


def test_all_no_projects_found(tmp_path, monkeypatch, capsys):
    """Test --all when no projects with workflows.yml exist."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["update_workflows", "--all"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    captured = capsys.readouterr()
    assert "No projects with .github/workflows.yml found" in captured.out
    assert exc_info.value.code == 1


def test_all_updates_files_in_multiple_projects(
    multi_project_workspace, mock_fetch, capsys, monkeypatch
):
    """Test --all actually creates/updates workflow files."""
    monkeypatch.setattr(sys, "argv", ["update_workflows", "--all"])

    exit_code = main()

    # Check files were created
    assert (
        multi_project_workspace / "project1" / ".github" / "workflows" / "test.yml"
    ).exists()
    assert (
        multi_project_workspace / "project2" / ".github" / "workflows" / "publish.yml"
    ).exists()
    assert (
        multi_project_workspace
        / "nested"
        / "project3"
        / ".github"
        / "workflows"
        / "python-test.yml"
    ).exists()

    # Verify content
    content1 = (
        multi_project_workspace / "project1" / ".github" / "workflows" / "test.yml"
    ).read_text()
    assert "name: Test" in content1

    assert exit_code == 0


# Tests for --commit option


def test_commit_creates_git_commit(
    temp_workspace, mock_fetch, mock_git, capsys, monkeypatch
):
    """Test --commit creates a git commit with proper message."""
    config_file = temp_workspace / ".github" / "workflows.yml"
    config_file.write_text("test: simonw/python-test\n")

    monkeypatch.setattr(sys, "argv", ["update_workflows", "--commit"])

    exit_code = main()

    # Check git commands were called
    assert mock_git.called

    # Get all the command calls
    all_calls = [str(call) for call in mock_git.call_args_list]

    # Should check if it's a git repo
    assert any("rev-parse" in call for call in all_calls)

    # Should add the file
    assert any("add" in call for call in all_calls)

    # Should commit - look for the actual commit command
    commit_calls = [
        call for call in all_calls if "'commit'" in call or '"commit"' in call
    ]
    assert len(commit_calls) > 0

    # Check output contains commit message
    captured = capsys.readouterr()
    assert "Committed: update-workflows: test.yml" in captured.out

    assert exit_code == 0


def test_commit_with_multiple_files(
    temp_workspace, mock_fetch, mock_git, capsys, monkeypatch
):
    """Test --commit message includes all updated files."""
    config_file = temp_workspace / ".github" / "workflows.yml"
    config_file.write_text(
        """test: simonw/python-test
publish: simonw/python-publish
"""
    )

    monkeypatch.setattr(sys, "argv", ["update_workflows", "--commit"])

    exit_code = main()

    # Check output contains commit message with both files
    captured = capsys.readouterr()
    assert "Committed: update-workflows:" in captured.out
    assert "test.yml" in captured.out
    assert "publish.yml" in captured.out


def test_commit_not_git_repo(temp_workspace, mock_fetch, capsys, monkeypatch):
    """Test --commit handles non-git repositories gracefully."""
    config_file = temp_workspace / ".github" / "workflows.yml"
    config_file.write_text("test: simonw/python-test\n")

    # Mock git to return error (not a git repo)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=128, stdout="", stderr="not a git repository"
        )

        monkeypatch.setattr(sys, "argv", ["update_workflows", "--commit"])

        exit_code = main()

        # Should still succeed but show warning
        captured = capsys.readouterr()
        assert "not a git repository" in captured.err or "Warning" in captured.out


def test_commit_fails_with_dry_run(temp_workspace, capsys, monkeypatch):
    """Test that --commit cannot be used with --dry-run."""
    config_file = temp_workspace / ".github" / "workflows.yml"
    config_file.write_text("test: simonw/python-test\n")

    monkeypatch.setattr(sys, "argv", ["update_workflows", "--dry-run", "--commit"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    captured = capsys.readouterr()
    assert "Cannot use --commit or --push with --dry-run" in captured.err
    assert exc_info.value.code == 1


# Tests for --push option


def test_push_implies_commit(temp_workspace, mock_fetch, mock_git, capsys, monkeypatch):
    """Test --push automatically enables --commit."""
    config_file = temp_workspace / ".github" / "workflows.yml"
    config_file.write_text("test: simonw/python-test\n")

    monkeypatch.setattr(sys, "argv", ["update_workflows", "--push"])

    exit_code = main()

    # Check both commit and push were called
    git_calls = [str(call) for call in mock_git.call_args_list]
    assert any("commit" in call for call in git_calls)
    assert any("push" in call for call in git_calls)


def test_push_fails_with_dry_run(temp_workspace, capsys, monkeypatch):
    """Test that --push cannot be used with --dry-run."""
    config_file = temp_workspace / ".github" / "workflows.yml"
    config_file.write_text("test: simonw/python-test\n")

    monkeypatch.setattr(sys, "argv", ["update_workflows", "--dry-run", "--push"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    captured = capsys.readouterr()
    assert "Cannot use --commit or --push with --dry-run" in captured.err
    assert exc_info.value.code == 1


# Tests for --all with --commit/--push


def test_all_with_commit(
    multi_project_workspace, mock_fetch, mock_git, capsys, monkeypatch
):
    """Test --all with --commit commits changes in each project."""
    monkeypatch.setattr(sys, "argv", ["update_workflows", "--all", "--commit"])

    exit_code = main()

    # Should have multiple commit calls (one per project with updates)
    commit_calls = [call for call in mock_git.call_args_list if "commit" in str(call)]
    assert len(commit_calls) >= 3  # At least one for each project

    captured = capsys.readouterr()
    assert "Committed:" in captured.out


def test_all_with_push(
    multi_project_workspace, mock_fetch, mock_git, capsys, monkeypatch
):
    """Test --all with --push pushes changes in each project."""
    monkeypatch.setattr(sys, "argv", ["update_workflows", "--all", "--push"])

    exit_code = main()

    # Should have push calls
    push_calls = [call for call in mock_git.call_args_list if "push" in str(call)]
    assert len(push_calls) >= 3  # At least one for each project

    captured = capsys.readouterr()
    assert "Pushed to remote" in captured.out


def test_commit_skips_unchanged_files(
    temp_workspace, mock_fetch, mock_git, capsys, monkeypatch
):
    """Test --commit doesn't commit when files are already up to date."""
    config_file = temp_workspace / ".github" / "workflows.yml"
    config_file.write_text("test: simonw/python-test\n")

    # Pre-create the file with the same content that would be fetched
    workflow_file = temp_workspace / ".github" / "workflows" / "test.yml"
    workflow_file.write_text(
        "name: Test\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest"
    )

    monkeypatch.setattr(sys, "argv", ["update_workflows", "--commit"])

    exit_code = main()

    # Should not create a commit since no files changed
    commit_calls = [call for call in mock_git.call_args_list if "commit" in str(call)]
    assert len(commit_calls) == 0

    captured = capsys.readouterr()
    assert "Already up to date" in captured.out
    assert exit_code == 1  # No files updated
