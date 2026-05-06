# Slimcraft Roadmap

## v0.1: Deterministic Dockerfile Scanner & LLM Rewrite (Dockerfile only)
- [x] Parse Dockerfile, analyze with AST
- [x] Detect bloat, root user, unpinned tags, missing multi-stage, etc.
- [x] CLI: `scan` command
- [x] CLI: `harden` command (LLM/PR stubs)
- [ ] Add more detection rules: secrets, .dockerignore, unnecessary build tools, etc.
- [ ] Add stubs for CVE/SBOM analysis (Trivy/Syft)
- [ ] Tests for all rules
- [ ] GitHub Actions for lint/test

## v0.2: Compose/Helm Image Reference Rewriting
- [ ] Parse Compose/Helm, detect image references
- [ ] Suggest/automate updates to use hardened images
- [ ] Tests for Compose/Helm

## v0.3: Policy Engine & Org Mode
- [ ] Org-wide policy checks (unpinned tags, root user, etc.)
- [ ] SaaS dashboard (optional), CLI remains 100% OSS
- [ ] Policy violation reports, dashboard MVP

---

## Production Readiness Checklist

- [ ] Real LLM integration (Anthropic/Ollama, not just stub)
- [ ] Actual PR creation (GitHub/GitLab API integration)
- [ ] Error handling for edge cases (file permissions, Docker daemon issues, etc.)
- [ ] Logging and debug output for troubleshooting
- [ ] Integration with Trivy, Syft, or other security scanners
- [ ] .dockerignore and secrets detection
- [ ] CI/CD pipeline (GitHub Actions) for linting, testing, packaging
- [ ] Packaging for Homebrew and pipx (release automation)
- [ ] User documentation beyond README (usage, config, troubleshooting)
- [ ] Versioning and release process
- [ ] Security review and dependency pinning

---

Acceptance criteria for each milestone are listed above. PRs and issues should reference the relevant milestone.
