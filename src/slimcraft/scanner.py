import os
import subprocess
import json
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
    import re
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

    from_instructions = [
        inst for inst in parser.structure if inst['instruction'] == 'FROM'
    ]
    results['is_multi_stage'] = len(from_instructions) > 1

    # 1. Missing multi-stage
    if not results['is_multi_stage']:
        results['warnings'].append({
            "severity": "High",
            "issue": "Single-stage build detected.",
            "recommendation": (
                "Use a multi-stage build to separate build "
                "tools from runtime."
            ),
        })

    # 2. Unpinned tags
    if parser.baseimage:
        no_tag = ':' not in parser.baseimage
        if no_tag or parser.baseimage.endswith(':latest'):
            results['warnings'].append({
                "severity": "Medium",
                "issue": f"Unpinned base image: {parser.baseimage}",
                "recommendation": (
                    "Pin to a specific SHA digest or version tag."
                ),
            })

    # 3. Bloated bases
    bloated_bases = ['ubuntu', 'debian', 'node', 'python', 'golang']
    if parser.baseimage:
        base_name = parser.baseimage.split(':')[0]
        slim_suffixes = ['-slim', '-alpine']
        is_slim = any(s in parser.baseimage for s in slim_suffixes)
        if base_name in bloated_bases and not is_slim:
            results['warnings'].append({
                "severity": "High",
                "issue": f"Potentially bloated base image: {parser.baseimage}",
                "recommendation": (
                    f"Switch to {base_name}-slim, alpine, "
                    "or a distroless/wolfi equivalent."
                ),
            })

    # 4. User Root
    user_instructions = [
        inst for inst in parser.structure if inst['instruction'] == 'USER'
    ]
    if not user_instructions:
        results['warnings'].append({
            "severity": "Critical",
            "issue": "Missing USER instruction. Container runs as root.",
            "recommendation": (
                "Add `USER nonroot` before the ENTRYPOINT."
            ),
        })
    elif user_instructions[-1]['value'].strip() == 'root':
        results['warnings'].append({
            "severity": "Critical",
            "issue": "Container explicitly set to run as root.",
            "recommendation": "Change to a non-root user.",
        })

    # Image size via Docker daemon (can fail independently)
    if parser.baseimage:
        size = get_image_size(parser.baseimage)
        if size:
            results["size_mb"] = size

    # Trivy and Syft (standalone binaries, don't need Docker)
    if parser.baseimage:
        trivy = run_trivy(parser.baseimage)
        if "error" not in trivy:
            results["cve_count"] = trivy["cve_count"]
            results["critical_cves"] = trivy["critical_count"]
        else:
            results["warnings"].append({
                "severity": "Low",
                "issue": "Trivy scan failed",
                "recommendation": (
                    "Install trivy (https://trivy.dev) "
                    "or check that it's in PATH."
                ),
            })
        syft = run_syft(parser.baseimage)
        if "error" not in syft:
            results["package_count"] = syft["package_count"]
        else:
            results["warnings"].append({
                "severity": "Low",
                "issue": "Syft scan failed",
                "recommendation": (
                    "Install syft (https://anchore.com/syft) "
                    "or check that it's in PATH."
                ),
            })

    # .dockerignore — check both Dockerfile dir and CWD
    dockerignore_candidates = [
        os.path.join(os.path.dirname(file_path), ".dockerignore"),
        os.path.join(os.getcwd(), ".dockerignore"),
    ]
    dockerignore_found = any(
        os.path.exists(p) for p in dockerignore_candidates
    )
    if not dockerignore_found:
        results["warnings"].append({
            "severity": "Medium",
            "issue": ".dockerignore file missing.",
            "recommendation": (
                "Add a .dockerignore to avoid leaking "
                "build context and secrets."
            ),
        })

    if detect_secrets(content):
        results["warnings"].append({
            "severity": "Critical",
            "issue": "Potential secret detected in Dockerfile.",
            "recommendation": (
                "Remove secrets from Dockerfile and use "
                "build-time ARGs or secrets management."
            ),
        })

    return results
