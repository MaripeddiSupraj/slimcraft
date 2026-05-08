from slimcraft.scanner import analyze_dockerfile


def test_analyze_dockerfile_missing():
    result = analyze_dockerfile("nonexistent_Dockerfile")
    assert "error" in result
    assert result["error"] == "Dockerfile not found."


def test_analyze_dockerfile_bloated(tmp_path):
    df_path = tmp_path / "Dockerfile"
    df_path.write_text("FROM node:18\nRUN echo 'hello'\nCMD ['npm', 'start']")
    (tmp_path / ".dockerignore").write_text("")

    result = analyze_dockerfile(str(df_path))
    assert result["base_image"] == "node:18"
    assert not result["is_multi_stage"]

    warnings = result["warnings"]
    assert len(warnings) == 7

    issues = [w["issue"] for w in warnings]
    assert "Single-stage build detected." in issues
    assert "Potentially bloated base image: node:18" in issues
    assert "Missing USER instruction. Container runs as root." in issues
    assert "Missing WORKDIR instruction." in issues
    assert "No HEALTHCHECK instruction." in issues
    assert "Trivy scan failed" in issues
    assert "Syft scan failed" in issues


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
    (tmp_path / ".dockerignore").write_text("")

    result = analyze_dockerfile(str(df_path))
    assert result["base_image"] == "cgr.dev/chainguard/node:latest"
    assert result["is_multi_stage"]

    warnings = result["warnings"]
    assert len(warnings) == 4

    issues = [w["issue"] for w in warnings]
    assert "Unpinned base image: cgr.dev/chainguard/node:latest" in issues
    assert "No HEALTHCHECK instruction." in issues
    assert "Trivy scan failed" in issues
    assert "Syft scan failed" in issues


def test_add_vs_copy(tmp_path):
    df_path = tmp_path / "Dockerfile"
    df_path.write_text("FROM alpine\nADD . /app\nCMD ['sh']")
    (tmp_path / ".dockerignore").write_text("")

    result = analyze_dockerfile(str(df_path))
    issues = [w["issue"] for w in warnings(result)]
    assert "ADD used where COPY would suffice." in issues


def test_apt_without_y(tmp_path):
    df_path = tmp_path / "Dockerfile"
    content = (
        "FROM ubuntu\n"
        "RUN apt-get update && apt-get install curl\n"
        "CMD ['bash']"
    )
    df_path.write_text(content)
    (tmp_path / ".dockerignore").write_text("")

    result = analyze_dockerfile(str(df_path))
    issues = [w["issue"] for w in warnings(result)]
    assert "apt-get without -y flag." in issues


def test_split_apt_update_install(tmp_path):
    df_path = tmp_path / "Dockerfile"
    content = (
        "FROM ubuntu\n"
        "RUN apt-get update\n"
        "RUN apt-get install -y curl\n"
        "CMD ['bash']"
    )
    df_path.write_text(content)
    (tmp_path / ".dockerignore").write_text("")

    result = analyze_dockerfile(str(df_path))
    issues = [w["issue"] for w in warnings(result)]
    assert "apt-get update and install are in separate RUN layers." in issues


def test_pip_no_cache(tmp_path):
    df_path = tmp_path / "Dockerfile"
    df_path.write_text("FROM python\nRUN pip install flask\nCMD ['python']")
    (tmp_path / ".dockerignore").write_text("")

    result = analyze_dockerfile(str(df_path))
    issues = [w["issue"] for w in warnings(result)]
    assert "pip install without --no-cache-dir." in issues


def test_expose_ssh(tmp_path):
    df_path = tmp_path / "Dockerfile"
    content = "FROM alpine\nRUN echo ok\nEXPOSE 22\nCMD ['sh']"
    df_path.write_text(content)
    (tmp_path / ".dockerignore").write_text("")

    result = analyze_dockerfile(str(df_path))
    issues = [w["issue"] for w in warnings(result)]
    assert "EXPOSE port 22 (SSH) detected." in issues


def test_chmod_777(tmp_path):
    df_path = tmp_path / "Dockerfile"
    content = "FROM alpine\nRUN chmod 777 /tmp\nCMD ['sh']"
    df_path.write_text(content)
    (tmp_path / ".dockerignore").write_text("")

    result = analyze_dockerfile(str(df_path))
    issues = [w["issue"] for w in warnings(result)]
    assert "RUN chmod 777 detected (world-writable permissions)." in issues


def test_apt_upgrade(tmp_path):
    df_path = tmp_path / "Dockerfile"
    content = "FROM ubuntu\nRUN apt-get upgrade -y\nCMD ['bash']"
    df_path.write_text(content)
    (tmp_path / ".dockerignore").write_text("")

    result = analyze_dockerfile(str(df_path))
    issues = [w["issue"] for w in warnings(result)]
    assert "apt-get upgrade or dist-upgrade detected." in issues


def test_apk_no_cache(tmp_path):
    df_path = tmp_path / "Dockerfile"
    content = "FROM alpine\nRUN apk add curl\nCMD ['sh']"
    df_path.write_text(content)
    (tmp_path / ".dockerignore").write_text("")

    result = analyze_dockerfile(str(df_path))
    issues = [w["issue"] for w in warnings(result)]
    assert "apk add without --no-cache." in issues


def warnings(result):
    return result.get("warnings", [])
