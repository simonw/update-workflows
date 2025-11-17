"""
Tests for update_workflows module.
"""

import pytest
import tempfile
import sys
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
from urllib.error import HTTPError, URLError

# Import the module to test
import update_workflows


class TestExtractTemplateReference:
    """Tests for extract_template_reference function."""

    def test_valid_reference(self, tmp_path):
        """Test extracting a valid template reference."""
        test_file = tmp_path / "workflow.yml"
        test_file.write_text("# user123/my-workflow\nname: Test\n")

        result = update_workflows.extract_template_reference(str(test_file))

        assert result == ("user123", "my-workflow")

    def test_reference_with_spaces(self, tmp_path):
        """Test extracting a reference with extra spaces."""
        test_file = tmp_path / "workflow.yml"
        test_file.write_text("#   user123/my-workflow  \nname: Test\n")

        result = update_workflows.extract_template_reference(str(test_file))

        assert result == ("user123", "my-workflow")

    def test_no_reference(self, tmp_path):
        """Test file without a template reference."""
        test_file = tmp_path / "workflow.yml"
        test_file.write_text("name: Test Workflow\non: push\n")

        result = update_workflows.extract_template_reference(str(test_file))

        assert result is None

    def test_invalid_format(self, tmp_path):
        """Test file with invalid reference format."""
        test_file = tmp_path / "workflow.yml"
        test_file.write_text("# invalid format\nname: Test\n")

        result = update_workflows.extract_template_reference(str(test_file))

        assert result is None

    def test_reference_not_on_first_line(self, tmp_path):
        """Test that reference on second line is not detected."""
        test_file = tmp_path / "workflow.yml"
        test_file.write_text("name: Test\n# user123/my-workflow\n")

        result = update_workflows.extract_template_reference(str(test_file))

        assert result is None

    def test_nonexistent_file(self, capsys):
        """Test handling of nonexistent file."""
        result = update_workflows.extract_template_reference("/nonexistent/file.yml")

        assert result is None
        captured = capsys.readouterr()
        assert "Error reading" in captured.err

    def test_empty_file(self, tmp_path):
        """Test handling of empty file."""
        test_file = tmp_path / "workflow.yml"
        test_file.write_text("")

        result = update_workflows.extract_template_reference(str(test_file))

        assert result is None


class TestBuildRemoteUrl:
    """Tests for build_remote_url function."""

    def test_build_url(self):
        """Test building a remote URL."""
        url = update_workflows.build_remote_url("myuser", "my-workflow")

        expected = "https://raw.githubusercontent.com/myuser/actions-workflows/refs/heads/main/my-workflow.yml"
        assert url == expected

    def test_build_url_with_special_chars(self):
        """Test building URL with special characters in workflow name."""
        url = update_workflows.build_remote_url("user", "test-workflow_v2")

        assert "test-workflow_v2.yml" in url


class TestFetchRemoteContent:
    """Tests for fetch_remote_content function."""

    @patch('urllib.request.urlopen')
    def test_successful_fetch(self, mock_urlopen):
        """Test successful content fetch."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"name: Test Workflow\non: push\n"
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        content = update_workflows.fetch_remote_content("https://example.com/workflow.yml")

        assert content == "name: Test Workflow\non: push\n"

    @patch('urllib.request.urlopen')
    def test_http_error(self, mock_urlopen, capsys):
        """Test handling of HTTP errors."""
        mock_urlopen.side_effect = HTTPError(
            "https://example.com/workflow.yml", 404, "Not Found", {}, None
        )

        content = update_workflows.fetch_remote_content("https://example.com/workflow.yml")

        assert content is None
        captured = capsys.readouterr()
        assert "HTTP Error 404" in captured.err

    @patch('urllib.request.urlopen')
    def test_url_error(self, mock_urlopen, capsys):
        """Test handling of URL errors."""
        mock_urlopen.side_effect = URLError("Connection failed")

        content = update_workflows.fetch_remote_content("https://example.com/workflow.yml")

        assert content is None
        captured = capsys.readouterr()
        assert "URL Error" in captured.err

    @patch('urllib.request.urlopen')
    def test_generic_exception(self, mock_urlopen, capsys):
        """Test handling of generic exceptions."""
        mock_urlopen.side_effect = Exception("Unknown error")

        content = update_workflows.fetch_remote_content("https://example.com/workflow.yml")

        assert content is None
        captured = capsys.readouterr()
        assert "Error fetching" in captured.err


class TestUpdateWorkflowFile:
    """Tests for update_workflow_file function."""

    @patch('update_workflows.extract_template_reference')
    def test_no_template_reference(self, mock_extract):
        """Test file without template reference is skipped."""
        mock_extract.return_value = None

        result = update_workflows.update_workflow_file("test.yml")

        assert result is False

    @patch('update_workflows.fetch_remote_content')
    @patch('update_workflows.extract_template_reference')
    def test_fetch_failure(self, mock_extract, mock_fetch, capsys):
        """Test handling of fetch failure."""
        mock_extract.return_value = ("user", "workflow")
        mock_fetch.return_value = None

        result = update_workflows.update_workflow_file("test.yml")

        assert result is False
        captured = capsys.readouterr()
        assert "Failed to fetch content" in captured.err

    @patch('update_workflows.fetch_remote_content')
    @patch('update_workflows.extract_template_reference')
    def test_dry_run_mode(self, mock_extract, mock_fetch, capsys):
        """Test dry-run mode doesn't modify files."""
        mock_extract.return_value = ("user", "workflow")
        mock_fetch.return_value = "name: New Content\n"

        result = update_workflows.update_workflow_file("test.yml", dry_run=True)

        assert result is True
        captured = capsys.readouterr()
        assert "[DRY RUN]" in captured.out

    @patch('update_workflows.fetch_remote_content')
    @patch('update_workflows.extract_template_reference')
    def test_successful_update(self, mock_extract, mock_fetch, tmp_path, capsys):
        """Test successful file update."""
        test_file = tmp_path / "workflow.yml"
        test_file.write_text("# user/workflow\nold content\n")

        mock_extract.return_value = ("user", "workflow")
        mock_fetch.return_value = "# user/workflow\nnew content\n"

        result = update_workflows.update_workflow_file(str(test_file))

        assert result is True
        assert test_file.read_text() == "# user/workflow\nnew content\n"
        captured = capsys.readouterr()
        assert "Successfully updated" in captured.out

    @patch('builtins.open', side_effect=PermissionError("Permission denied"))
    @patch('update_workflows.fetch_remote_content')
    @patch('update_workflows.extract_template_reference')
    def test_write_error(self, mock_extract, mock_fetch, mock_open_func, capsys):
        """Test handling of write errors."""
        mock_extract.return_value = ("user", "workflow")
        mock_fetch.return_value = "new content"

        result = update_workflows.update_workflow_file("test.yml")

        assert result is False
        captured = capsys.readouterr()
        assert "Error writing" in captured.err


class TestMain:
    """Tests for main CLI function."""

    @patch('sys.argv', ['update-workflows', '--workflows-dir', '/nonexistent'])
    def test_nonexistent_directory(self, capsys):
        """Test handling of nonexistent workflows directory."""
        with pytest.raises(SystemExit) as exc_info:
            update_workflows.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "does not exist" in captured.err

    @patch('sys.argv', ['update-workflows'])
    def test_no_workflow_files(self, tmp_path, capsys, monkeypatch):
        """Test handling of directory with no workflow files."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            update_workflows.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "No workflow files found" in captured.out

    @patch('update_workflows.update_workflow_file')
    @patch('sys.argv', ['update-workflows'])
    def test_successful_updates(self, mock_update, tmp_path, capsys, monkeypatch):
        """Test successful workflow updates."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "test1.yml").write_text("# user/workflow1\n")
        (workflows_dir / "test2.yml").write_text("# user/workflow2\n")
        monkeypatch.chdir(tmp_path)

        mock_update.return_value = True

        result = update_workflows.main()

        assert result == 0
        assert mock_update.call_count == 2

    @patch('update_workflows.update_workflow_file')
    @patch('sys.argv', ['update-workflows', '--dry-run'])
    def test_dry_run_flag(self, mock_update, tmp_path, monkeypatch):
        """Test --dry-run flag is passed correctly."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "test.yml").write_text("# user/workflow\n")
        monkeypatch.chdir(tmp_path)

        mock_update.return_value = True

        result = update_workflows.main()

        # Verify dry_run was passed as True
        # Path is relative from working directory after chdir
        mock_update.assert_called_with(".github/workflows/test.yml", dry_run=True)
        assert result == 0

    @patch('update_workflows.update_workflow_file')
    @patch('sys.argv', ['update-workflows', '--workflows-dir', 'custom/path'])
    def test_custom_workflows_dir(self, mock_update, tmp_path, monkeypatch):
        """Test custom workflows directory."""
        custom_dir = tmp_path / "custom" / "path"
        custom_dir.mkdir(parents=True)
        (custom_dir / "test.yml").write_text("# user/workflow\n")
        monkeypatch.chdir(tmp_path)

        mock_update.return_value = True

        result = update_workflows.main()

        assert mock_update.call_count == 1
        assert result == 0

    @patch('update_workflows.update_workflow_file')
    @patch('sys.argv', ['update-workflows'])
    def test_yaml_extension_support(self, mock_update, tmp_path, monkeypatch):
        """Test that both .yml and .yaml files are processed."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "test1.yml").write_text("# user/workflow1\n")
        (workflows_dir / "test2.yaml").write_text("# user/workflow2\n")
        monkeypatch.chdir(tmp_path)

        mock_update.return_value = True

        result = update_workflows.main()

        assert mock_update.call_count == 2
        assert result == 0

    @patch('update_workflows.update_workflow_file')
    @patch('sys.argv', ['update-workflows'])
    def test_no_updates_exit_code(self, mock_update, tmp_path, monkeypatch):
        """Test exit code when no files are updated."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "test.yml").write_text("name: Test\n")
        monkeypatch.chdir(tmp_path)

        mock_update.return_value = False

        result = update_workflows.main()

        assert result == 1
