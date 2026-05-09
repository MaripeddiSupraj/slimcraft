from unittest.mock import patch

from slimcraft.llm import (
    llm_rewrite_dockerfile,
    _parse_llm_response,
    _build_user_message,
    _validate_dockerfile,
)


def test_build_user_message():
    msg = _build_user_message("FROM node:18")
    assert "FROM node:18" in msg
    assert "```dockerfile" in msg


def test_parse_response_full():
    text = """```dockerfile
FROM alpine:3.20
CMD ["sh"]
```

## Rationale
Switched to alpine, added non-root user."""
    rewritten, rationale, err = _parse_llm_response(text)
    assert err is None
    assert "FROM alpine:3.20" in rewritten
    assert "Switched to alpine" in rationale


def test_parse_response_no_rationale():
    text = """```dockerfile
FROM alpine:3.20
```"""
    rewritten, rationale, err = _parse_llm_response(text)
    assert err is None
    assert rationale == "LLM rewrite applied."


def test_parse_response_no_code_block():
    text = "Just some text without a code block"
    rewritten, rationale, err = _parse_llm_response(text)
    assert err is not None
    assert "Could not parse Dockerfile" in err


def test_missing_file():
    rewritten, err = llm_rewrite_dockerfile("/nonexistent/Dockerfile")
    assert rewritten is None
    assert "Dockerfile not found" in err


def test_no_api_key(tmp_path):
    df = tmp_path / "Dockerfile"
    df.write_text("FROM node:18")
    with patch("slimcraft.llm.getenv", return_value=None):
        rewritten, err = llm_rewrite_dockerfile(str(df))
        assert rewritten is None
        assert "ANTHROPIC_API_KEY not set" in err


SAMPLE_RESPONSE = """```dockerfile
FROM node:18-slim AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

FROM cgr.dev/chainguard/node:latest
USER nonroot
WORKDIR /app
COPY --from=builder /app /app
CMD ["node", "server.js"]
```

## Rationale
- Split into multi-stage build
- Used chainguard/node base for 0 CVEs
- Added non-root user
"""


def test_anthropic_import_error(tmp_path):
    df = tmp_path / "Dockerfile"
    df.write_text("FROM node:18")
    with (
        patch("slimcraft.llm.getenv", return_value="sk-fake"),
        patch(
            "slimcraft.llm._call_anthropic",
            return_value=(
                None,
                "anthropic package not installed. "
                "Run: pip install slimcraft[llm]"
            ),
        ),
    ):
        rewritten, err = llm_rewrite_dockerfile(str(df))
        assert rewritten is None
        assert "pip install slimcraft[llm]" in err


def test_ollama_connection_error(tmp_path):
    df = tmp_path / "Dockerfile"
    df.write_text("FROM node:18")
    with (
        patch("slimcraft.llm.getenv", return_value="http://localhost:11434"),
        patch(
            "slimcraft.llm._call_ollama",
            return_value=(
                None,
                "Cannot connect to Ollama at http://localhost:11434. "
                "Is Ollama running?"
            ),
        ),
    ):
        rewritten, err = llm_rewrite_dockerfile(
            str(df), model="local:qwen2.5-coder"
        )
        assert rewritten is None
        assert "Cannot connect to Ollama" in err


def test_ollama_no_httpx(tmp_path):
    df = tmp_path / "Dockerfile"
    df.write_text("FROM node:18")
    with (
        patch("slimcraft.llm.getenv", return_value="http://localhost:11434"),
        patch(
            "slimcraft.llm._call_ollama",
            return_value=(
                None, "httpx is required for Ollama. Run: pip install httpx"
            ),
        ),
    ):
        rewritten, err = llm_rewrite_dockerfile(
            str(df), model="local:qwen2.5-coder"
        )
        assert rewritten is None
        assert "httpx is required" in err


def test_anthropic_success(tmp_path):
    df = tmp_path / "Dockerfile"
    df.write_text("FROM node:18\nCMD ['node', 'server.js']")

    with (
        patch("slimcraft.llm.getenv", return_value="sk-fake-key"),
        patch(
            "slimcraft.llm._call_anthropic",
            return_value=(SAMPLE_RESPONSE, None),
        ),
    ):
        rewritten, rationale = llm_rewrite_dockerfile(str(df))

    assert rewritten is not None
    assert "FROM node:18-slim" in rewritten
    assert "cgr.dev/chainguard/node" in rewritten
    assert "multi-stage" in rationale.lower()


def test_ollama_success(tmp_path):
    df = tmp_path / "Dockerfile"
    df.write_text("FROM node:18\nCMD ['node', 'server.js']")

    with patch(
        "slimcraft.llm._call_ollama",
        return_value=(SAMPLE_RESPONSE, None),
    ):
        rewritten, rationale = llm_rewrite_dockerfile(
            str(df), model="local:qwen2.5-coder"
        )

    assert rewritten is not None
    assert "FROM node:18-slim" in rewritten
    assert "multi-stage" in rationale.lower()


def test_llm_invalid_output_rejected(tmp_path):
    df = tmp_path / "Dockerfile"
    df.write_text("FROM node:18")

    invalid = """```dockerfile
    # just a comment — no valid instructions
    ```
    ## Rationale
    Garbage"""

    with (
        patch("slimcraft.llm.getenv", return_value="sk-fake"),
        patch(
            "slimcraft.llm._call_anthropic",
            return_value=(invalid, None),
        ),
    ):
        rewritten, err = llm_rewrite_dockerfile(str(df))
        assert rewritten is None
        assert "invalid dockerfile" in err.lower()


def test_validate_dockerfile_valid():
    _validate_dockerfile("FROM alpine:3.20\nCMD [\"sh\"]\n")


def test_validate_dockerfile_empty():
    import pytest
    with pytest.raises(ValueError, match="invalid Dockerfile"):
        _validate_dockerfile("")
