import json as json_lib
import click
from rich.console import Console
from rich.table import Table
import logging

from slimcraft.scanner import analyze_dockerfile
from slimcraft.llm import llm_rewrite_dockerfile
from slimcraft.pr_utils import open_pr_with_diff
from slimcraft.docker_utils import build_image
from slimcraft.config import load_env
from slimcraft.fixer import fix_dockerfile, fix_dockerignore

console = Console()

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("slimcraft")


@click.group()
@click.option(
    '-v', '--verbose', count=True,
    help="Increase verbosity (-v info, -vv debug)"
)
@click.pass_context
def main(ctx, verbose):
    """Agentic container hardening that you can actually trust."""
    if verbose == 1:
        logging.getLogger("slimcraft").setLevel(logging.INFO)
    elif verbose >= 2:
        logging.getLogger("slimcraft").setLevel(logging.DEBUG)
    if verbose:
        logger.info("Verbose mode enabled (level=%s)", verbose)
    load_env()
    ctx.ensure_object(dict)
    ctx.obj["VERBOSE"] = verbose


def _exit_code(results):
    """Return non-zero if scan found warnings with severity >= Medium."""
    warnings = results.get("warnings", [])
    sev_map = {
        "Critical": 3, "High": 2, "Medium": 1, "Low": 0, "Warning": 0
    }
    max_sev = 0
    for w in warnings:
        s = w.get("severity", "Warning")
        max_sev = max(max_sev, sev_map.get(s, 0))
    return max_sev


@main.command()
@click.argument(
    'dockerfile_path', type=click.Path(exists=True, dir_okay=False)
)
@click.option(
    '--format', 'fmt', type=click.Choice(['table', 'json']),
    default='table', help="Output format"
)
@click.option(
    '--build', is_flag=True,
    help="Build the Dockerfile and report image size/layers"
)
def scan(dockerfile_path, fmt, build):
    """Scan a Dockerfile for bloat and vulnerabilities."""
    try:
        path = dockerfile_path
        if fmt == 'table':
            console.print(f"[bold blue]Scanning {path}...[/bold blue]")
        with console.status("Analyzing AST and Layers..."):
            results = analyze_dockerfile(path)

        if build:
            with console.status("Building image..."):
                build_info = build_image(path)
                if build_info and "error" not in build_info:
                    results["build_size_mb"] = build_info["size_mb"]
                    results["build_layers"] = build_info["layers"]
                elif build_info:
                    results["build_error"] = build_info["error"]

        if "error" in results:
            if fmt == 'json':
                click.echo(json_lib.dumps({"error": results['error']}))
            else:
                err = results['error']
                console.print(f"[bold red]Error: {err}[/bold red]")
            logger.error("Scan error: %s", results['error'])
            raise SystemExit(1)

        if fmt == 'json':
            click.echo(json_lib.dumps(results, indent=2, default=str))
            raise SystemExit(_exit_code(results))

        console.print("[bold green]Scan complete![/bold green]\n")

        mt = Table(title="Image Metrics")
        mt.add_column("Metric", style="cyan")
        mt.add_column("Value", style="magenta")
        mt.add_row("Base Image", results.get("base_image", "Unknown"))
        multi = "Yes" if results.get("is_multi_stage") else "[red]No[/red]"
        mt.add_row("Multi-stage", multi)
        if results.get("size_mb") is not None:
            mt.add_row("Base Image Size", f"{results['size_mb']:.2f} MB")
        if results.get("build_size_mb") is not None:
            mt.add_row("Build Size", f"{results['build_size_mb']:.2f} MB")
        if results.get("build_layers") is not None:
            mt.add_row("Layers", str(results["build_layers"]))
        if results.get("cve_count") is not None:
            mt.add_row("CVEs", str(results["cve_count"]))
        if results.get("critical_cves") is not None:
            mt.add_row("Critical CVEs", str(results["critical_cves"]))
        if results.get("package_count") is not None:
            mt.add_row("Package Count", str(results["package_count"]))
        console.print(mt)
        console.print()

        if results.get("build_error"):
            console.print(f"[red]Build error: {results['build_error']}[/red]")

        warnings = results.get("warnings", [])
        if warnings:
            wt = Table(title="Anti-Patterns Detected", show_lines=True)
            wt.add_column("Severity", style="red", justify="center")
            wt.add_column("Issue", style="yellow")
            wt.add_column("Recommendation", style="green")
            for w in warnings:
                sev = w.get("severity", "Warning")
                wt.add_row(sev, w["issue"], w["recommendation"])
            console.print(wt)
        else:
            console.print(
                "[bold green]No obvious anti-patterns detected![/bold green]"
            )

        raise SystemExit(_exit_code(results))
    except SystemExit:
        raise
    except Exception as e:
        logger.exception("Exception during scan: %s", e)
        console.print(f"[bold red]Unexpected error: {e}[/bold red]")
        raise SystemExit(1)


@main.command()
@click.argument(
    'dockerfile_path', type=click.Path(exists=True, dir_okay=False)
)
@click.option(
    '--rewrite', is_flag=True, help="Use LLM to rewrite the Dockerfile"
)
@click.option(
    '--model', default=None,
    help=(
        'Model to use for rewrite. '
        '"anthropic:default" or "local:qwen2.5-coder". '
        'Defaults to ANTHROPIC_API_KEY or SLIMCRAFT_MODEL env var.'
    ),
)
@click.option(
    '--pr', is_flag=True, help="Open a Pull Request with the rewrite"
)
def harden(dockerfile_path, rewrite, model, pr):
    """Harden a Dockerfile using agentic rewriting."""
    try:
        path = dockerfile_path
        console.print(f"[bold blue]Hardening {path}...[/bold blue]")
        if not rewrite:
            msg = "--rewrite flag not set. Only deterministic scan available."
            console.print(f"[yellow]{msg}[/yellow]")
            return
        with console.status("Calling LLM..."):
            rewritten, rationale = llm_rewrite_dockerfile(
                path, model=model
            )
        if rewritten:
            console.print("[green]Dockerfile rewritten![/green]")
            console.print("[bold]Rationale:[/bold] " + rationale)
            if pr:
                open_pr_with_diff(path, rewritten, rationale)
        else:
            msg = f"[yellow]LLM rewrite not available: {rationale}[/yellow]"
            console.print(msg)
    except Exception as e:
        logger.exception("Exception during harden: %s", e)
        console.print(f"[bold red]Unexpected error: {e}[/bold red]")
        raise SystemExit(1)


@main.command()
@click.argument(
    'dockerfile_path', type=click.Path(exists=True, dir_okay=False)
)
@click.option(
    '--write', is_flag=True,
    help="Write fixes back to the file (default: print to stdout)"
)
def fix(dockerfile_path, write):
    """Apply deterministic fixes to a Dockerfile (no LLM needed)."""
    try:
        path = dockerfile_path
        console.print(f"[bold blue]Fixing {path}...[/bold blue]")

        with open(path) as f:
            original = f.read()

        fixed, changes = fix_dockerfile(original)

        di_created = fix_dockerignore(path)

        if not changes and not di_created:
            console.print(
                "[green]No fixes needed. Dockerfile is clean![/green]"
            )
            return

        if changes:
            console.print(f"[green]Made {len(changes)} fix(es):[/green]")
            for c in changes:
                console.print(
                    f"  [cyan]{c['id']}[/cyan] — {c['description']} "
                    f"({c['count']} occurrence{'s' if c['count'] > 1 else ''})"
                )

        if di_created:
            console.print(
                "  [cyan]dockerignore[/cyan] — Created .dockerignore file"
            )

        if write:
            with open(path, 'w') as f:
                f.write(fixed)
            console.print(f"[green]Written to {path}[/green]")
        else:
            console.print("\n[bold]--- Fixed Dockerfile ---[/bold]")
            click.echo(fixed)
    except Exception as e:
        logger.exception("Exception during fix: %s", e)
        console.print(f"[bold red]Unexpected error: {e}[/bold red]")
        raise SystemExit(1)


if __name__ == '__main__':
    main()
