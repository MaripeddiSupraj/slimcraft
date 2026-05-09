import os
import subprocess
import json
import re
from dockerfile_parse import DockerfileParser
from slimcraft.docker_utils import get_image_size


def run_trivy(image_name):
    """Run Trivy on the given image and return CVE summary."""
    try:
        result = subprocess.run([
            "trivy", "image", "--quiet", "--format", "json", image_name
        ], capture_output=True, text=True)
        data = json.loads(result.stdout)
        cve_count = 0
        critical_count = 0
        for r in data.get("Results", []):
            for vuln in r.get("Vulnerabilities", []):
                cve_count += 1
                if vuln.get("Severity") == "CRITICAL":
                    critical_count += 1
        return {"cve_count": cve_count, "critical_count": critical_count}
    except Exception as e:
        return {"error": f"Trivy scan failed: {e}"}


def run_syft(image_name):
    """Run Syft to generate SBOM and return package count."""
    try:
        result = subprocess.run([
            "syft", image_name, "-o", "json"
        ], capture_output=True, text=True)
        data = json.loads(result.stdout)
        pkgs = data.get("artifacts", [])
        return {"package_count": len(pkgs)}
    except Exception as e:
        return {"error": f"Syft scan failed: {e}"}


def detect_secrets(content):
    """Detect common secrets in Dockerfile content."""
    patterns = [
        r'(?i)AWS_ACCESS_KEY_ID',
        r'(?i)AWS_SECRET_ACCESS_KEY',
        r'(?i)GOOGLE_APPLICATION_CREDENTIALS',
        r'(?i)password\s*=\s*[^\s]+',
        r'(?i)secret\s*=\s*[^\s]+',
        r'(?i)token\s*=\s*[^\s]+',
    ]
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        for pat in patterns:
            if re.search(pat, stripped):
                return True
    return False


def _find_instructions(structure, instruction):
    return [
        inst for inst in structure if inst['instruction'] == instruction
    ]


def _any_run_matches(run_instructions, pattern):
    for inst in run_instructions:
        if re.search(pattern, inst['value']):
            return True
    return False


def _warn(results, severity, issue, recommendation):
    results["warnings"].append({
        "severity": severity,
        "issue": issue,
        "recommendation": recommendation,
    })


def analyze_dockerfile(file_path: str) -> dict:
    """Parse the Dockerfile and run deterministic heuristic checks."""
    if not os.path.exists(file_path):
        return {"error": "Dockerfile not found."}

    with open(file_path, 'r') as f:
        content = f.read()

    parser = DockerfileParser()
    parser.content = content

    results = {
        "base_image": parser.baseimage,
        "is_multi_stage": False,
        "warnings": [],
        "size_mb": None,
    }

    structure = parser.structure

    from_instructions = _find_instructions(structure, 'FROM')
    run_instructions = _find_instructions(structure, 'RUN')
    results['is_multi_stage'] = len(from_instructions) > 1

    # 1. Missing multi-stage
    if not results['is_multi_stage']:
        _warn(results, "High",
              "Single-stage build detected.",
              "Use a multi-stage build to separate build tools from runtime.")

    # 2. Unpinned tags
    if parser.baseimage:
        no_tag = ':' not in parser.baseimage
        if no_tag or parser.baseimage.endswith(':latest'):
            _warn(results, "Medium",
                  f"Unpinned base image: {parser.baseimage}",
                  "Pin to a specific SHA digest or version tag.")

    # 3. Bloated bases
    bloated_bases = ['ubuntu', 'debian', 'node', 'python', 'golang']
    if parser.baseimage:
        base_name = parser.baseimage.split(':')[0]
        is_slim = any(s in parser.baseimage for s in ['-slim', '-alpine'])
        if base_name in bloated_bases and not is_slim:
            _warn(results, "High",
                  f"Potentially bloated base image: {parser.baseimage}",
                  f"Switch to {base_name}-slim, alpine, "
                  "or distroless/wolfi equivalent.")

    # 4. Root user
    user_instructions = _find_instructions(structure, 'USER')
    if not user_instructions:
        _warn(results, "Critical",
              "Missing USER instruction. Container runs as root.",
              "Add `USER nonroot` before the ENTRYPOINT.")
    elif user_instructions[-1]['value'].strip() == 'root':
        _warn(results, "Critical",
              "Container explicitly set to run as root.",
              "Change to a non-root user.")

    # 5. ADD vs COPY
    add_instructions = _find_instructions(structure, 'ADD')
    for add in add_instructions:
        val = add['value']
        if not re.search(r'^(https?://|--chown=)', val or ''):
            _warn(results, "Medium",
                  "ADD used where COPY would suffice.",
                  "Prefer COPY over ADD unless you need "
                  "URL fetching or tar auto-extraction.")
            break

    # 6. apt-get without -y
    if _any_run_matches(run_instructions, r'apt-get (?!.*-y)'):
        _warn(results, "Medium",
              "apt-get without -y flag.",
              "Add `-y` to apt-get to avoid interactive prompts.")

    # 7. Split apt-get update / install
    run_vals = [inst['value'] for inst in run_instructions]
    has_update = any('apt-get update' in v for v in run_vals)
    has_install = any('apt-get install' in v for v in run_vals)
    if has_update and has_install:
        combined = any(
            'apt-get update' in v and 'apt-get install' in v
            for v in run_vals
        )
        if not combined:
            _warn(results, "Medium",
                  "apt-get update and install are in separate RUN layers.",
                  "Combine into one RUN: "
                  "`apt-get update && apt-get install -y pkg && ...`")

    # 8. pip install without --no-cache-dir
    pip_no_cache = r'pip\s+install(?!.*--no-cache-dir)'
    if _any_run_matches(run_instructions, pip_no_cache):
        _warn(results, "Low",
              "pip install without --no-cache-dir.",
              "Add `--no-cache-dir` to pip install to reduce image size.")

    # 9. npm install without npm ci
    if _any_run_matches(run_instructions, r'(?<!\w)npm\s+install(?!.*ci)'):
        lock_exists = os.path.exists(
            os.path.join(os.path.dirname(file_path), "package-lock.json")
        )
        if lock_exists:
            _warn(results, "Medium",
                  "npm install should use npm ci when lockfile exists.",
                  "Use `npm ci` instead of `npm install` "
                  "for deterministic builds.")
        else:
            _warn(results, "Low",
                  "npm install without lockfile.",
                  "Commit package-lock.json and use `npm ci` instead.")

    # 10. apk add without --no-cache
    apk_re = r'apk\s+add(?!.*--no-cache)'
    if _any_run_matches(run_instructions, apk_re):
        _warn(results, "Low",
              "apk add without --no-cache.",
              "Add `--no-cache` to apk add to reduce image size.")

    # 11. EXPOSE 22 (SSH)
    expose_instructions = _find_instructions(structure, 'EXPOSE')
    for exp in expose_instructions:
        if '22' in (exp.get('value') or '').split():
            _warn(results, "Critical",
                  "EXPOSE port 22 (SSH) detected.",
                  "Remove SSH exposure. "
                  "Use docker exec for debugging.")
            break

    # 12. Missing WORKDIR
    workdir_instructions = _find_instructions(structure, 'WORKDIR')
    if not workdir_instructions:
        _warn(results, "Medium",
              "Missing WORKDIR instruction.",
              "Add `WORKDIR /app` (or similar) before COPY/RUN commands.")

    # 13. chmod 777
    if _any_run_matches(run_instructions, r'chmod\s+777'):
        _warn(results, "Critical",
              "RUN chmod 777 detected (world-writable permissions).",
              "Use more restrictive permissions (e.g., chmod 755 or 644).")

    # 14. apt-get upgrade
    upgrade_re = r'apt-get\s+(upgrade|dist-upgrade)'
    if _any_run_matches(run_instructions, upgrade_re):
        _warn(results, "Medium",
              "apt-get upgrade or dist-upgrade detected.",
              "Pin specific package versions instead of upgrading all. "
              "Upgrades can break reproducibility.")

    # 15. No HEALTHCHECK
    healthcheck = _find_instructions(structure, 'HEALTHCHECK')
    if not healthcheck:
        _warn(results, "Low",
              "No HEALTHCHECK instruction.",
              "Add a HEALTHCHECK for container orchestration "
              "to detect unhealthy states.")

    # 16. CMD/ENTRYPOINT string form (should use exec form)
    for instr in ['CMD', 'ENTRYPOINT']:
        for inst in _find_instructions(structure, instr):
            val = (inst.get('value') or '').strip()
            if val and not val.startswith('[') and not val.startswith('"'):
                _warn(results, "Medium",
                      f"{instr} uses shell form instead of exec form.",
                      f"Use exec form: `{instr} [\"executable\", \"arg\"]`")
                break

    # 17. Multiple ENV vars on single line
    env_instructions = _find_instructions(structure, 'ENV')
    for env in env_instructions:
        val = (env.get('value') or '').strip()
        if ' ' in val and '=' in val:
            parts = val.split()
            eq_count = sum(1 for p in parts if '=' in p)
            if eq_count > 1:
                _warn(results, "Low",
                      "Multiple ENV vars defined on a single line.",
                      "Use one ENV per line for better layer caching.")
                break

    # 18. No LABEL
    if not _find_instructions(structure, 'LABEL'):
        _warn(results, "Low",
              "No LABEL instruction.",
              "Add LABEL for metadata (maintainer, version, description).")

    # 19. yum/zypper/dnf without -y
    for pkg_mgr in ['yum', 'zypper', 'dnf']:
        ptn = rf'{pkg_mgr}\s+(install|update)(?!.*-y)'
        if _any_run_matches(run_instructions, ptn):
            _warn(results, "Medium",
                  f"{pkg_mgr} install/update without -y flag.",
                  f"Add `-y` to {pkg_mgr} to avoid interactive prompts.")
            break

    # 20. curl | bash or wget | sh
    pipe_shell = r'(curl|wget)\s+.*\s*\|\s*(bash|sh)'
    if _any_run_matches(run_instructions, pipe_shell):
        _warn(results, "Critical",
              "Piped curl/wget to shell detected.",
              "Download and verify the script separately "
              "instead of piping to shell.")

    # 21. COPY without --chown when non-root USER exists
    if user_instructions:
        last_user = user_instructions[-1]['value'].strip()
        if last_user != 'root':
            copy_instructions = _find_instructions(structure, 'COPY')
            for cp in copy_instructions:
                if '--from=' in (cp.get('value') or ''):
                    continue
                if '--chown=' not in (cp.get('value') or ''):
                    _warn(results, "Medium",
                          "COPY without --chown flag.",
                          f"Add `--chown={last_user}` "
                          "to maintain correct file ownership.")
                    break

    # Image size via Docker daemon
    if parser.baseimage:
        size = get_image_size(parser.baseimage)
        if size:
            results["size_mb"] = size

    # Trivy and Syft
    if parser.baseimage:
        trivy = run_trivy(parser.baseimage)
        if "error" not in trivy:
            results["cve_count"] = trivy["cve_count"]
            results["critical_cves"] = trivy["critical_count"]
        else:
            _warn(results, "Low", "Trivy scan failed",
                  "Install trivy (https://trivy.dev) "
                  "or check that it's in PATH.")
        syft = run_syft(parser.baseimage)
        if "error" not in syft:
            results["package_count"] = syft["package_count"]
        else:
            _warn(results, "Low", "Syft scan failed",
                  "Install syft (https://anchore.com/syft) "
                  "or check that it's in PATH.")

    # .dockerignore
    dockerignore_candidates = [
        os.path.join(os.path.dirname(file_path), ".dockerignore"),
        os.path.join(os.getcwd(), ".dockerignore"),
    ]
    if not any(os.path.exists(p) for p in dockerignore_candidates):
        _warn(results, "Medium",
              ".dockerignore file missing.",
              "Add a .dockerignore to avoid leaking build context.")

    # Secrets
    if detect_secrets(content):
        _warn(results, "Critical",
              "Potential secret detected in Dockerfile.",
              "Remove secrets from Dockerfile. "
              "Use build-time ARGs or secrets management.")

    return results
