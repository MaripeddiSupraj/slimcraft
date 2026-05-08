<div align="center">
  <h1>🛡️ slimcraft</h1>
  <p><b>Agentic container hardening that you can actually trust.</b></p>

  <p>
    <a href="https://github.com/MaripeddiSupraj/slimcraft/actions"><img src="https://img.shields.io/github/actions/workflow/status/MaripeddiSupraj/slimcraft/ci.yml" alt="Build Status"></a>
    <a href="https://pypi.org/project/slimcraft/"><img src="https://img.shields.io/pypi/v/slimcraft.svg" alt="PyPI Version"></a>
    <a href="https://github.com/MaripeddiSupraj/slimcraft/blob/main/LICENSE"><img src="https://img.shields.io/github/license/MaripeddiSupraj/slimcraft" alt="License"></a>
  </p>
</div>

`slimcraft` is a deterministic-first CLI that scans your Dockerfiles, identifies bloat and vulnerabilities, and uses LLMs to rewrite them into secure, multi-stage, zero-CVE builds—automatically opening a PR with the rationale.

*Stop staring at 500 CVEs in Trivy. Let `slimcraft` fix them for you.*

## ✨ The 60-Second Demo

```bash
# 1. Scan your bloated Dockerfile deterministically (No LLM)
$ slimcraft scan ./Dockerfile
🔍 Analyzing node:18 base...
⚠️  USER root detected
⚠️  Size: 1.2 GB
🚨 CVEs: 483 (12 Critical)

# 2. Let the agent rewrite it
$ slimcraft harden ./Dockerfile --rewrite
🤖 Reasoning: Node app can run on chainguard/node...
♻️  Rewriting to multi-stage build...

# 3. Open a PR with the changes
$ slimcraft harden ./Dockerfile --rewrite --pr
🚀 PR Opened: https://github.com/org/repo/pull/42
```

**Before (`1.2GB`, `483 CVEs`):**
```dockerfile
FROM node:18
WORKDIR /app
COPY . .
RUN npm install
CMD ["npm", "start"]
```

**After (`140MB`, `0 CVEs`):**
```dockerfile
FROM node:18 AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

FROM cgr.dev/chainguard/node:latest
WORKDIR /app
COPY --from=builder /app /app
CMD ["npm", "start"]
```

## 🚀 Why Slimcraft?

*   **Deterministic Core:** Real AST parsing and Trivy/Syft integration. The LLM is strictly gated behind `--rewrite`.
*   **Safe by Default:** The rewritten Dockerfile is validated before it's suggested.
*   **Privacy First:** Run purely locally using Ollama (`--model local:qwen2.5-coder`), or use the Anthropic API. Proprietary Dockerfiles don't have to leave your laptop.

## 📦 Installation

**Via Pipx (Recommended for Python users):**
```bash
pipx install slimcraft
```

**With LLM support (Anthropic + Ollama):**
```bash
pipx install slimcraft[llm]
```

## 🛠️ Quickstart

**1. Scan a Dockerfile (Deterministic, no LLM)**
```bash
slimcraft scan path/to/Dockerfile
```

**2. Rewrite it via Anthropic**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
slimcraft harden path/to/Dockerfile --rewrite
```

**3. Rewrite via local Ollama**
```bash
slimcraft harden path/to/Dockerfile --rewrite --model local:qwen2.5-coder
```

**4. Rewrite and open a GitHub PR**
```bash
slimcraft harden path/to/Dockerfile --rewrite --pr
```

## ⚙️ Configuration

All config via environment variables or `.env` file:

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | API key for Anthropic LLM |
| `SLIMCRAFT_MODEL` | `anthropic:default` | Default model to use |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `GH_TOKEN` | — | GitHub token for PR creation |

slimcraft loads `.env` from the current directory and `~/.slimcraft/.env`.

## 🧪 Running Tests

```bash
pip install slimcraft[dev]
pytest
```

---
*Built with ❤️ for DevOps engineers who want to sleep at night.*
