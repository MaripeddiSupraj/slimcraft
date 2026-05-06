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
        ], capture_output=True, text=True, check=True)
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
        ], capture_output=True, text=True, check=True)
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
        r'(?i)password\s*=\s*.+',
        r'(?i)secret\s*=\s*.+',
        r'(?i)token\s*=\s*.+',
    ]
    for pat in patterns:
        if re.search(pat, content):
            return True
    return False

def analyze_dockerfile(file_path: str) -> dict:
    """
    Parses the Dockerfile and runs deterministic heuristic checks.
    """
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
        "size_mb": None
    }
    
    # Check Multi-stage
    # dockerfile_parse doesn't perfectly expose multiple FROMs easily in a single property,
    # but we can count the FROM instructions
    from_instructions = [inst for inst in parser.structure if inst['instruction'] == 'FROM']
    results['is_multi_stage'] = len(from_instructions) > 1
    
    # 1. Rule: Missing multi-stage
    if not results['is_multi_stage']:
        results['warnings'].append({
            "severity": "High",
            "issue": "Single-stage build detected.",
            "recommendation": "Use a multi-stage build to separate build tools from runtime."
        })
        
    # 2. Rule: Unpinned tags
    if parser.baseimage:
        if ':' not in parser.baseimage or parser.baseimage.endswith(':latest'):
            results['warnings'].append({
                "severity": "Medium",
                "issue": f"Unpinned base image: {parser.baseimage}",
                "recommendation": "Pin to a specific SHA digest or version tag."
            })
            
    # 3. Rule: Bloated bases
    bloated_bases = ['ubuntu', 'debian', 'node', 'python', 'golang']
    if parser.baseimage:
        base_name = parser.baseimage.split(':')[0]
        if base_name in bloated_bases and not any(suffix in parser.baseimage for suffix in ['-slim', '-alpine']):
            results['warnings'].append({
                "severity": "High",
                "issue": f"Potentially bloated base image: {parser.baseimage}",
                "recommendation": f"Switch to {base_name}-slim, alpine, or a distroless/wolfi equivalent."
            })
            
    # 4. Rule: User Root
    # Check if USER instruction exists and the last one is not root
    user_instructions = [inst for inst in parser.structure if inst['instruction'] == 'USER']
    if not user_instructions:
        results['warnings'].append({
            "severity": "Critical",
            "issue": "Missing USER instruction. Container runs as root.",
            "recommendation": "Add `USER nonroot` or similar before the ENTRYPOINT."
        })
    elif user_instructions[-1]['value'].strip() == 'root':
        results['warnings'].append({
            "severity": "Critical",
            "issue": "Container explicitly set to run as root.",
            "recommendation": "Change to a non-root user."
        })
        
    # Attempt to get image size if we can build it (or if it's already built)
    # For now, let's just attempt to see if the base image size is known or we can get local size
    # We will build the user's directory optionally if they want layer analysis.
    # For v0.1 basic scan, we might just fetch the base image size.
    try:
        if parser.baseimage:
            size = get_image_size(parser.baseimage)
            if size:
                results["size_mb"] = size
            # Trivy and Syft integration
            trivy = run_trivy(parser.baseimage)
            if "error" not in trivy:
                results["cve_count"] = trivy["cve_count"]
                results["critical_cves"] = trivy["critical_count"]
            else:
                results["cve_count"] = None
                results["critical_cves"] = None
                results["warnings"].append({
                    "severity": "Low",
                    "issue": "Trivy scan failed",
                    "recommendation": trivy["error"]
                })
            syft = run_syft(parser.baseimage)
            if "error" not in syft:
                results["package_count"] = syft["package_count"]
            else:
                results["package_count"] = None
                results["warnings"].append({
                    "severity": "Low",
                    "issue": "Syft scan failed",
                    "recommendation": syft["error"]
                })
    except Exception as e:
        # Docker not running or image not found locally without pull
        pass

    # .dockerignore check
    dockerignore_path = os.path.join(os.path.dirname(file_path), ".dockerignore")
    if not os.path.exists(dockerignore_path):
        results["warnings"].append({
            "severity": "Medium",
            "issue": ".dockerignore file missing.",
            "recommendation": "Add a .dockerignore to avoid leaking build context and secrets."
        })
    # Secrets detection
    if detect_secrets(content):
        results["warnings"].append({
            "severity": "Critical",
            "issue": "Potential secret detected in Dockerfile.",
            "recommendation": "Remove secrets from Dockerfile and use build-time ARGs or secrets management."
        })

    return results
