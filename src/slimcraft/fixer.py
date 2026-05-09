import os


def _run_line_has(content, marker):
    """Check if a RUN line contains marker without the flag."""
    lines = content.splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped.upper().startswith("RUN "):
            continue
        if marker in stripped:
            return True
    return False


def fix_apt_get(content):
    """Add -y to apt-get install if missing."""
    count = 0
    lines = content.splitlines(True)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.upper().startswith("RUN "):
            continue
        if "apt-get install" not in stripped:
            continue
        if "-y" in stripped:
            continue
        occ = stripped.count("apt-get install")
        lines[i] = line.replace("apt-get install", "apt-get install -y")
        count += occ
    return "".join(lines), count


def fix_pip(content):
    """Add --no-cache-dir to pip install if missing."""
    count = 0
    lines = content.splitlines(True)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.upper().startswith("RUN "):
            continue
        if "pip install" not in stripped:
            continue
        if "--no-cache-dir" in stripped:
            continue
        occ = stripped.count("pip install")
        lines[i] = line.replace("pip install", "pip install --no-cache-dir")
        count += occ
    return "".join(lines), count


def fix_apk(content):
    """Add --no-cache to apk add if missing."""
    count = 0
    lines = content.splitlines(True)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.upper().startswith("RUN "):
            continue
        if "apk add" not in stripped:
            continue
        if "--no-cache" in stripped:
            continue
        occ = stripped.count("apk add")
        lines[i] = line.replace("apk add", "apk add --no-cache")
        count += occ
    return "".join(lines), count


def fix_yum(content):
    """Add -y to yum/dnf/zypper install/update if missing."""
    count = 0
    lines = content.splitlines(True)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.upper().startswith("RUN "):
            continue
        if "-y" in stripped:
            continue
        for cmd in ("yum", "dnf", "zypper"):
            for op in ("install", "update"):
                token = f"{cmd} {op}"
                if token not in stripped:
                    continue
                occ = stripped.count(token)
                lines[i] = line.replace(token, f"{token} -y")
                count += occ
    return "".join(lines), count


def fix_user(content):
    """Add USER nonroot before CMD/ENTRYPOINT if no USER exists."""
    lines = content.splitlines()
    users = [x for x in lines if x.strip().upper().startswith("USER ")]
    if users:
        return content, 0

    n = len(lines)
    insert_at = n
    for i in range(n - 1, -1, -1):
        stripped = lines[i].strip()
        upper = stripped.upper()
        if upper.startswith("CMD ") or upper.startswith("ENTRYPOINT "):
            insert_at = i

    lines.insert(insert_at, "USER nonroot")
    return "\n".join(lines) + "\n", 1


def fix_workdir(content):
    """Add WORKDIR /app after FROM if missing."""
    lines = content.splitlines()
    workdirs = [x for x in lines if x.strip().upper().startswith("WORKDIR ")]
    if workdirs:
        return content, 0

    insert_at = 1
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("FROM "):
            insert_at = i + 1
            break

    lines.insert(insert_at, "WORKDIR /app")
    return "\n".join(lines) + "\n", 1


def fix_dockerignore(file_path):
    """Create .dockerignore alongside Dockerfile if missing."""
    df_dir = os.path.dirname(os.path.abspath(file_path))
    di_path = os.path.join(df_dir, ".dockerignore")
    if os.path.exists(di_path):
        return False
    with open(di_path, 'w') as f:
        f.write("node_modules/\n.git/\n*.md\n.env\nvenv/\n__pycache__/\n")
    return True


FIXES = [
    ("apt-y", "Add -y to apt-get install", fix_apt_get),
    ("pip-cache", "Add --no-cache-dir to pip install", fix_pip),
    ("apk-cache", "Add --no-cache to apk add", fix_apk),
    ("yum-y", "Add -y to yum/dnf/zypper install/update", fix_yum),
    ("user", "Add USER nonroot before CMD/ENTRYPOINT", fix_user),
    ("workdir", "Add WORKDIR /app", fix_workdir),
]


def fix_dockerfile(content):
    """Apply all deterministic fixes to Dockerfile content.
    Returns (fixed_content, changes) where changes is a list of dicts.
    """
    fixed = content
    changes = []

    for fix_id, desc, fix_fn in FIXES:
        candidate, count = fix_fn(fixed)
        if count > 0:
            changes.append({
                "id": fix_id,
                "description": desc,
                "count": count,
            })
            fixed = candidate

    return fixed, changes
