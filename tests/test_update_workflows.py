"""Simple CLI tests for update_workflows."""

import pytest
from pathlib import Path
from update_workflows import main
import sys


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    """Create a temporary workspace with workflows directory."""
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)

    # Change to temp directory
    monkeypatch.chdir(tmp_path)

    return tmp_path


@pytest.mark.parametrize("config_content,expected_count", [
    # List format
    ("""- simonw/python-test
- simonw/python-publish
""", 2),
    # Dict format with custom filenames
    ("""test: simonw/python-test
publish: simonw/python-publish
""", 2),
    # Single item list
    ("""- simonw/python-test
""", 1),
])
def test_dry_run_with_different_config_formats(temp_workspace, capsys, monkeypatch, config_content, expected_count):
    """Test dry-run with different YAML config formats."""
    # Create config file
    config_file = temp_workspace / ".github" / "workflows.yml"
    config_file.write_text(config_content)

    # Mock sys.argv for argparse
    monkeypatch.setattr(sys, 'argv', ['update_workflows', '--dry-run'])

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
    monkeypatch.setattr(sys, 'argv', ['update_workflows'])

    # Run without creating config file
    with pytest.raises(SystemExit) as exc_info:
        main()

    # Should exit with error
    captured = capsys.readouterr()
    assert "not found" in captured.err
    assert exc_info.value.code == 1


def test_custom_workflows_dir(temp_workspace, capsys, monkeypatch):
    """Test using a custom workflows directory."""
    # Create custom directory
    custom_dir = temp_workspace / "custom" / "workflows"
    custom_dir.mkdir(parents=True)

    # Create config
    config_file = temp_workspace / ".github" / "workflows.yml"
    config_file.write_text("- simonw/python-test\n")

    # Mock sys.argv with custom directory
    monkeypatch.setattr(sys, 'argv', [
        'update_workflows',
        '--dry-run',
        '--workflows-dir', str(custom_dir)
    ])

    # Run the command
    exit_code = main()

    # Should succeed
    captured = capsys.readouterr()
    assert "[DRY RUN]" in captured.out
    assert exit_code == 0


def test_empty_config_file(temp_workspace, capsys, monkeypatch):
    """Test behavior with empty config file."""
    # Create empty config
    config_file = temp_workspace / ".github" / "workflows.yml"
    config_file.write_text("")

    # Mock sys.argv
    monkeypatch.setattr(sys, 'argv', ['update_workflows'])

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
    monkeypatch.setattr(sys, 'argv', ['update_workflows'])

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
    monkeypatch.setattr(sys, 'argv', ['update_workflows'])

    # Run the command
    with pytest.raises(SystemExit) as exc_info:
        main()

    # Should exit with error
    captured = capsys.readouterr()
    assert "does not exist" in captured.err
    assert exc_info.value.code == 1
