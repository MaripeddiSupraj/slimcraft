import os
import re
import logging

from slimcraft.config import getenv

logger = logging.getLogger("slimcraft")

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
DEFAULT_OLLAMA_MODEL = "qwen2.5-coder"

SYSTEM_PROMPT = (
    "You are a container security expert. "
    "Rewrite Dockerfiles to be more secure and smaller.\n\n"
    "Rules:\n"
    "1. Use multi-stage builds to separate build tools from runtime\n"
    "2. Switch to distroless, wolfi, or slim base images when possible\n"
    "3. Add a non-root user (USER nonroot) before CMD/ENTRYPOINT\n"
    "4. Pin base image versions to specific tags or SHA digests\n"
    "5. Combine RUN commands to reduce layer count\n"
    "6. Use --no-cache / -y / clean flags to minimize image size\n"
    "7. Only copy necessary artifacts from builder stages\n"
    "8. Use lockfiles for deterministic installs\n"
    "9. Remove build-time deps not needed at runtime\n"
    "10. Never include secrets, tokens, or credentials\n\n"
    "Return your response in EXACTLY this format "
    "(use the exact section headers):\n\n"
    "```dockerfile\n"
    "<rewritten Dockerfile content>\n"
    "```\n\n"
    "## Rationale\n"
    "<bullet-point explanation of what changed and why>"
)


def _build_user_message(content):
    return (
        "Here is the Dockerfile to rewrite:\n\n"
        f"```dockerfile\n{content}\n```"
    )


def _parse_llm_response(text):
    """Extract rewritten Dockerfile and rationale from LLM response."""
    df_match = re.search(
        r"```(?:dockerfile)?\s*\n(.*?)```", text, re.DOTALL
    )
    if not df_match:
        return None, None, "Could not parse Dockerfile from response."

    rewritten = df_match.group(1).strip()

    rationale_match = re.search(
        r"## Rationale\s*\n(.*)", text, re.DOTALL
    )
    rationale = (
        rationale_match.group(1).strip()
        if rationale_match
        else "LLM rewrite applied."
    )

    return rewritten, rationale, None


def _call_anthropic(api_key, model, system, messages):
    """Call the Anthropic API and return the response text."""
    try:
        import anthropic
    except ImportError:
        return None, (
            "anthropic package not installed. "
            "Run: pip install slimcraft[llm]"
        )

    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        temperature=0,
        system=system,
        messages=messages,
    )

    text = "".join(
        block.text for block in response.content if block.type == "text"
    )
    return text, None


def _call_ollama(model, system, messages):
    """Call a local Ollama instance via HTTP."""
    try:
        import httpx
    except ImportError:
        return None, "httpx is required for Ollama. Run: pip install httpx"

    base_url = getenv("OLLAMA_HOST", "http://localhost:11434")
    url = f"{base_url.rstrip('/')}/api/chat"

    payload = {
        "model": model.replace("local:", "", 1),
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            *messages,
        ],
    }

    try:
        resp = httpx.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        text = data.get("message", {}).get("content", "")
        return text, None
    except httpx.ConnectError:
        return None, (
            f"Cannot connect to Ollama at {base_url}. "
            "Is Ollama running?"
        )
    except Exception as e:
        return None, f"Ollama request failed: {e}"


def llm_rewrite_dockerfile(dockerfile_path, model=None):
    """
    Rewrite a Dockerfile using an LLM (Anthropic or Ollama).

    Returns (rewritten_content, rationale) on success,
    or (None, error_message) on failure.
    """
    if not os.path.exists(dockerfile_path):
        return None, f"Dockerfile not found: {dockerfile_path}"

    with open(dockerfile_path) as f:
        content = f.read()

    model = model or getenv("SLIMCRAFT_MODEL") or "anthropic:default"
    user_message = _build_user_message(content)
    messages = [{"role": "user", "content": user_message}]

    if model.startswith("local:"):
        text, err = _call_ollama(model, SYSTEM_PROMPT, messages)
    else:
        api_key = getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return None, (
                "ANTHROPIC_API_KEY not set. "
                "Set it in your environment or .env file."
            )
        anthropic_model = (
            DEFAULT_ANTHROPIC_MODEL
            if model == "anthropic:default"
            else model
        )
        text, err = _call_anthropic(
            api_key, anthropic_model, SYSTEM_PROMPT, messages
        )

    if err:
        return None, err
    if not text:
        return None, "LLM returned an empty response."

    rewritten, rationale, parse_err = _parse_llm_response(text)
    if parse_err:
        logger.debug("Raw LLM response: %s", text[:500])
        return None, parse_err

    logger.info(
        "LLM rewrite complete (%d chars -> %d chars)",
        len(content), len(rewritten)
    )
    return rewritten, rationale
