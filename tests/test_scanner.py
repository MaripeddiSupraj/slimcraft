import os
import pytest
from slimcraft.scanner import analyze_dockerfile

def test_analyze_dockerfile_missing():
    result = analyze_dockerfile("nonexistent_Dockerfile")
    assert "error" in result
    assert result["error"] == "Dockerfile not found."

def test_analyze_dockerfile_bloated(tmp_path):
    df_path = tmp_path / "Dockerfile"
    df_path.write_text("FROM node:18\nRUN echo 'hello'\nCMD ['npm', 'start']")
    
    result = analyze_dockerfile(str(df_path))
    assert result["base_image"] == "node:18"
    assert not result["is_multi_stage"]
    
    warnings = result["warnings"]
    assert len(warnings) == 3
    
    issues = [w["issue"] for w in warnings]
    assert "Single-stage build detected." in issues
    assert "Potentially bloated base image: node:18" in issues
    assert "Missing USER instruction. Container runs as root." in issues

def test_analyze_dockerfile_clean(tmp_path):
    df_path = tmp_path / "Dockerfile"
    content = """
    FROM node:18-slim AS builder
    WORKDIR /app
    COPY . .
    
    FROM cgr.dev/chainguard/node:latest
    USER nonroot
    COPY --from=builder /app /app
    CMD ["npm", "start"]
    """
    df_path.write_text(content)
    
    result = analyze_dockerfile(str(df_path))
    assert result["base_image"] == "cgr.dev/chainguard/node:latest"
    assert result["is_multi_stage"]
    
    # Missing USER is fixed. Multi-stage is fixed. Base image is chainguard, which is not in the bloated list.
    warnings = result["warnings"]
    assert len(warnings) == 1
    # The only warning should be unpinned tag because :latest is used
    assert warnings[0]["issue"] == "Unpinned base image: cgr.dev/chainguard/node:latest"
