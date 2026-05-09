from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run for trivy (Results) and syft (artifacts)."""

    def _side_effect(cmd, *args, **kwargs):
        if cmd[0] == 'trivy':
            stdout = '{"Results": []}'
        elif cmd[0] == 'syft':
            stdout = '{"artifacts": []}'
        else:
            stdout = ""
        return MagicMock(stdout=stdout, returncode=0)

    with patch("slimcraft.scanner.subprocess.run") as mock:
        mock.side_effect = _side_effect
        yield mock


@pytest.fixture
def mock_docker():
    """Mock docker client to simulate no Docker daemon."""
    with patch("slimcraft.docker_utils.docker.from_env") as mock:
        mock.side_effect = Exception("Docker not available")
        yield mock


@pytest.fixture
def mock_gh_auth():
    """Mock gh auth check to appear authenticated."""
    with (
        patch("slimcraft.pr_utils._is_git_repo", return_value=True),
        patch("slimcraft.pr_utils._gh_authenticated", return_value=True),
        patch("slimcraft.pr_utils._dirty_warning", return_value=False),
    ):
        yield


@pytest.fixture
def sample_dockerfile_bloated(tmp_path):
    """Create a bloated example Dockerfile."""
    df = tmp_path / "Dockerfile"
    df.write_text("FROM node:18\nRUN echo 'hello'\nCMD ['npm', 'start']")
    (tmp_path / ".dockerignore").write_text("")
    return str(df)


@pytest.fixture
def sample_dockerfile_clean(tmp_path):
    """Create a clean example Dockerfile."""
    df = tmp_path / "Dockerfile"
    content = """
    FROM node:18-slim AS builder
    WORKDIR /app
    COPY . .

    FROM cgr.dev/chainguard/node:latest
    USER nonroot
    COPY --from=builder /app /app
    CMD ["npm", "start"]
    """
    df.write_text(content)
    (tmp_path / ".dockerignore").write_text("")
    return str(df)
