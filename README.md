<div align="center">
  <h1>🛡️ slimcraft</h1>
  <p><b>Agentic container hardening that you can actually trust.</b></p>

  <p>
    <a href="https://github.com/MaripeddiSupraj/slimcraft/actions"><img src="https://img.shields.io/github/actions/workflow/status/MaripeddiSupraj/slimcraft/ci.yml" alt="CI"></a>
    <a href="https://pypi.org/project/slimcraft/"><img src="https://img.shields.io/pypi/v/slimcraft.svg" alt="PyPI"></a>
    <a href="https://pypi.org/project/slimcraft/"><img src="https://img.shields.io/pypi/pyversions/slimcraft.svg" alt="Python"></a>
    <a href="https://github.com/MaripeddiSupraj/slimcraft/blob/main/LICENSE"><img src="https://img.shields.io/github/license/MaripeddiSupraj/slimcraft" alt="License"></a>
    <a href="https://github.com/MaripeddiSupraj/slimcraft"><img src="https://img.shields.io/github/stars/MaripeddiSupraj/slimcraft?style=social" alt="Stars"></a>
  </p>
</div>

`slimcraft` scans your Dockerfiles for bloat and vulnerabilities, applies deterministic fixes in seconds, and optionally rewrites them into minimal, secure builds using an LLM — all without leaving your terminal.

> Stop staring at 483 CVEs. Let `slimcraft` fix them for you.

---

## Features

| | Feature | Description |
|---|---|---|
| 🔍 | **Scan** | 24 built-in detection rules + Trivy CVE scanning + Syft SBOM analysis |
| 🔧 | **Fix** | Deterministic auto-fix without any LLM — write safe Dockerfiles in seconds |
| 🤖 | **Harden** | LLM-powered rewrite with multi-stage builds, distroless bases, zero CVEs |
| 🚀 | **PR** | Open a GitHub PR with the rewritten Dockerfile and rationale |
| 🏠 | **Local-first** | Works fully offline via Ollama — proprietary code never leaves your machine |

---

## Quickstart

### 1. Scan a Dockerfile

```bash
slimcraft scan Dockerfile
```

Detects 24 anti-patterns (ADD vs COPY, missing `-y`, shell-form CMD, etc.) plus CVE count and base image size.

```bash
slimcraft scan Dockerfile --format json    # JSON output for CI pipelines
slimcraft scan Dockerfile --build           # Build image and report size + layers
```

### 2. Fix it deterministically

```bash
slimcraft fix Dockerfile                    # print fixed version to stdout
slimcraft fix Dockerfile --write            # overwrite file in-place
```

No LLM, no API calls. Safe, deterministic transformations:

| Fix | Rule |
|---|---|
| `apt-get install` → `apt-get install -y` | Non-interactive installs |
| `pip install` → `pip install --no-cache-dir` | Reduce layer size |
| `apk add` → `apk add --no-cache` | Alpine best practice |
| `yum/dnf/zypper install` → add `-y` | Non-interactive installs |
| Missing `WORKDIR /app` → added after `FROM` | Standardize working dir |
| Missing `USER nonroot` → added before `CMD` | Drop root privileges |
| Missing `.dockerignore` → created alongside | Exclude build context cruft |

### 3. Harden with an LLM

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
slimcraft harden Dockerfile --rewrite
```

Or use a local model:

```bash
slimcraft harden Dockerfile --rewrite --model local:qwen2.5-coder
```

The LLM rewrites your Dockerfile into a secure multi-stage build, then explains every change.

### 4. Open a PR

```bash
slimcraft harden Dockerfile --rewrite --pr
```

Creates a branch, commits the rewrite, pushes, and opens a PR using the `gh` CLI.

---

## Before vs. After

**Before** (`1.2 GB`, `483 CVEs`, `root` user):
```dockerfile
FROM node:18
WORKDIR /app
COPY . .
RUN npm install
CMD ["npm", "start"]
```

**After** (`140 MB`, `0 CVEs`, `nonroot` user):
```dockerfile
FROM node:18 AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .

FROM cgr.dev/chainguard/node:latest
WORKDIR /app
COPY --from=builder /app /app
USER nonroot
CMD ["npm", "start"]
```

The agent explains: *"Split into multi-stage, switched to distroless base, dropped dev dependencies, and added nonroot user."*

---

## Installation

```bash
pip install slimcraft           # base install (scan + fix)
pip install slimcraft[llm]      # + Anthropic + Ollama support
```

Or via pipx:

```bash
pipx install slimcraft
pipx install slimcraft[llm]     # with LLM extras
```

Requires Python 3.9+.

---

## CLI Reference

### `slimcraft scan`

```bash
Usage: slimcraft scan [OPTIONS] DOCKERFILE_PATH

Scan a Dockerfile for bloat and vulnerabilities.

Options:
  --format [table|json]  Output format (default: table)
  --build                Build image and report size + layers
  -v, -vv                Increase verbosity
  --help                 Show this message
```

Exit codes:
| Code | Meaning |
|---|---|
| `0` | No issues or only Low/Warning |
| `1` | Medium severity issues found |
| `2` | High severity issues found |
| `3` | Critical severity issues found |

### `slimcraft fix`

```bash
Usage: slimcraft fix [OPTIONS] DOCKERFILE_PATH

Apply deterministic fixes to a Dockerfile (no LLM needed).

Options:
  --write  Write fixes back to the file (default: print to stdout)
  --help   Show this message
```

### `slimcraft harden`

```bash
Usage: slimcraft harden [OPTIONS] DOCKERFILE_PATH

Harden a Dockerfile using agentic rewriting.

Options:
  --rewrite        Use LLM to rewrite the Dockerfile
  --model TEXT     Model to use (anthropic:default or local:<model>)
  --pr             Open a Pull Request with the rewrite
  --help           Show this message
```

---

## Detection Rules (24)

| # | Rule | Severity |
|---|---|---|
| 1 | Single-stage build detected | High |
| 2 | Potentially bloated base image | High |
| 3 | Missing `.dockerignore` | High |
| 4 | `ADD` used instead of `COPY` | Medium |
| 5 | `apt-get install` without `-y` | Medium |
| 6 | `apt-get update` and `install` in separate layers | Medium |
| 7 | `pip install` without `--no-cache-dir` | Medium |
| 8 | Missing npm/yarn lockfile | Medium |
| 9 | `apk add` without `--no-cache` | Medium |
| 10 | Port 22 exposed (SSH) | Medium |
| 11 | `chmod 777` detected | Medium |
| 12 | `apt-get upgrade` in Dockerfile | Medium |
| 13 | Secrets in build args or env | High |
| 14 | Shell-form `CMD` instead of exec-form | Medium |
| 15 | Shell-form `ENTRYPOINT` instead of exec-form | Medium |
| 16 | Multiple `ENV` on one line | Low |
| 17 | Missing `LABEL` | Low |
| 18 | `yum/dnf/zypper` without `-y` | Medium |
| 19 | `curl ... \| sh` security risk | High |
| 20 | `COPY` without `--chown` | Low |
| 21 | Missing `WORKDIR` | Medium |
| 22 | Missing `USER` (runs as root) | High |
| 23 | No `HEALTHCHECK` | Low |
| 24 | Missing Trivy/Syft scan info | Info |

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | API key for Anthropic Claude |
| `SLIMCRAFT_MODEL` | `anthropic:default` | Default LLM model |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen2.5-coder` | Default Ollama model |
| `GH_TOKEN` | — | GitHub token for PR creation |

`.env` files are loaded from the current directory and `~/.slimcraft/.env`.

---

## CI/CD Integration

### GitHub Actions

```yaml
- name: Scan Dockerfile
  run: slimcraft scan Dockerfile --format json
  continue-on-error: true
```

### Pre-commit

```yaml
# .pre-commit-config.yaml
- repo: https://github.com/MaripeddiSupraj/slimcraft
  rev: v0.1.0
  hooks:
    - id: slimcraft-scan
```

Fails commits that introduce High+ severity issues.

### Exit Codes in CI

Exit code is non-zero when Medium+ severity issues are found — fail builds on real problems, allow Low/Warning to pass:

```bash
slimcraft scan Dockerfile --format json || echo "Issues found (exit $?)"
```

---

## Architecture

```
                    ┌──────────────┐
                    │  Dockerfile   │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         ┌────────┐  ┌──────────┐  ┌────────┐
         │ Scan   │  │ Fix      │  │ Harden │
         │ (AST)  │  │ (regex)  │  │ (LLM)  │
         └───┬────┘  └────┬─────┘  └───┬────┘
             │            │            │
             ▼            ▼            ▼
       ┌──────────┐  ┌────────┐  ┌──────────┐
       │ Trivy    │  │ Write  │  │ Anthropic│
       │ Syft     │  │ stdout │  │ Ollama   │
       │ Docker   │  │ --write│  │ gh PR    │
       └──────────┘  └────────┘  └──────────┘
```

---

## Development

```bash
git clone https://github.com/MaripeddiSupraj/slimcraft.git
cd slimcraft
pip install -e ".[dev]"
pytest           # 84+ tests
flake8 src/ tests/
```

---

## License

MIT

---

<div align="center">
  <sub>Built for DevOps engineers who want to sleep at night.</sub>
</div>
