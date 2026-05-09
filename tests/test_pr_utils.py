from unittest.mock import patch, MagicMock
import subprocess

from slimcraft.pr_utils import open_pr_with_diff


def mock_run(cmd_map, errors=None):
    """Build a side effect for subprocess.run from a command->stdout map.
    errors is a set of command prefixes that should raise CalledProcessError.
    """
    errors = errors or set()

    def _side_effect(cmd, *args, **kwargs):
        cmd_str = " ".join(cmd)
        for prefix in errors:
            if cmd_str.startswith(prefix):
                raise subprocess.CalledProcessError(1, cmd)
        stdout = cmd_map.get(cmd_str, "")
        m = MagicMock(stdout=stdout, returncode=0)
        return m
    return _side_effect


def test_not_git_repo():
    cmd_map = {"git rev-parse --git-dir": ""}
    with patch("slimcraft.pr_utils.subprocess.run") as mock:
        mock.side_effect = mock_run(cmd_map)
        result = open_pr_with_diff("Dockerfile", "content", "reason")
        assert result is False


def test_not_authenticated():
    cmd_map = {
        "git rev-parse --git-dir": ".git\n",
        "gh auth status": "",
    }
    with patch("slimcraft.pr_utils.subprocess.run") as mock:
        mock.side_effect = mock_run(cmd_map)
        result = open_pr_with_diff("Dockerfile", "content", "reason")
        assert result is False


def test_identical_content(tmp_path):
    df = tmp_path / "Dockerfile"
    df.write_text("same content")
    cmd_map = {
        "git rev-parse --git-dir": ".git\n",
        "gh auth status": "Logged in to github.com\n",
        "git status --porcelain": "",
    }
    with patch("slimcraft.pr_utils.subprocess.run") as mock:
        mock.side_effect = mock_run(cmd_map)
        result = open_pr_with_diff(str(df), "same content", "reason")
        assert result is False


def test_successful_pr(tmp_path):
    df = tmp_path / "Dockerfile"
    df.write_text("original content")
    cmd_map = {
        "git rev-parse --git-dir": ".git\n",
        "gh auth status": "Logged in to github.com\n",
        "git status --porcelain": "",
        "git checkout -b": "",
        "git add": "",
        "git commit -m": "",
        "git push": "",
        "gh pr create": "https://github.com/org/repo/pull/42\n",
        "git checkout -": "",
    }
    with patch("slimcraft.pr_utils.subprocess.run") as mock:
        mock.side_effect = mock_run(cmd_map)
        result = open_pr_with_diff(str(df), "rewritten", "fixed CVEs")
        assert result is True


def test_failed_push_restores(tmp_path):
    df = tmp_path / "Dockerfile"
    df.write_text("original content")
    cmd_map = {
        "git rev-parse --git-dir": ".git\n",
        "gh auth status": "Logged in to github.com\n",
        "git status --porcelain": "",
        "git checkout -b": "",
        "git add": "",
        "git commit -m": "",
        "git checkout -": "",
        "git branch -D": "",
    }
    errors = {"git push"}
    with patch("slimcraft.pr_utils.subprocess.run") as mock:
        mock.side_effect = mock_run(cmd_map, errors)
        result = open_pr_with_diff(str(df), "rewritten", "fixed CVEs")
        assert result is False
        assert df.read_text() == "original content"
