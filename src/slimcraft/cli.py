import click
from rich.console import Console
from rich.table import Table
import logging

from slimcraft.scanner import analyze_dockerfile
from slimcraft.llm import llm_rewrite_dockerfile
from slimcraft.pr_utils import open_pr_with_diff
from slimcraft.config import load_env

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


@main.command()
@click.argument(
    'dockerfile_path', type=click.Path(exists=True, dir_okay=False)
)
def scan(dockerfile_path):
    """Scan a Dockerfile for bloat and vulnerabilities."""
    try:
        path = dockerfile_path
        console.print(f"[bold blue]🔍 Scanning {path}...[/bold blue]")
        with console.status("Analyzing AST and Layers..."):
            results = analyze_dockerfile(path)
        if "error" in results:
            console.print(f"[bold red]❌ Error: {results['error']}[/bold red]")
            logger.error("Scan error: %s", results['error'])
            return
        console.print("[bold green]✅ Scan complete![/bold green]\n")

        mt = Table(title="Image Metrics")
        mt.add_column("Metric", style="cyan")
        mt.add_column("Value", style="magenta")
        mt.add_row("Base Image", results.get("base_image", "Unknown"))
        multi = "Yes" if results.get("is_multi_stage") else "[red]No[/red]"
        mt.add_row("Multi-stage", multi)
        if results.get("size_mb") is not None:
            mt.add_row("Image Size", f"{results['size_mb']:.2f} MB")
        if results.get("cve_count") is not None:
            mt.add_row("CVEs", str(results["cve_count"]))
        if results.get("critical_cves") is not None:
            mt.add_row("Critical CVEs", str(results["critical_cves"]))
        if results.get("package_count") is not None:
            mt.add_row("Package Count", str(results["package_count"]))
        console.print(mt)
        console.print()

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
    except Exception as e:
        logger.exception("Exception during scan: %s", e)
        console.print(f"[bold red]❌ Unexpected error: {e}[/bold red]")


@main.command()
@click.argument(
    'dockerfile_path', type=click.Path(exists=True, dir_okay=False)
)
@click.option(
    '--rewrite', is_flag=True, help="Use LLM to rewrite the Dockerfile"
)
@click.option(
    '--pr', is_flag=True, help="Open a Pull Request with the rewrite"
)
def harden(dockerfile_path, rewrite, pr):
    """Harden a Dockerfile using agentic rewriting."""
    try:
        path = dockerfile_path
        console.print(f"[bold blue]🔒 Hardening {path}...[/bold blue]")
        if not rewrite:
            msg = "--rewrite flag not set. Only deterministic scan available."
            console.print(f"[yellow]{msg}[/yellow]")
            return
        rewritten, rationale = llm_rewrite_dockerfile(path)
        if rewritten:
            console.print("[green]🤖 Dockerfile rewritten![/green]")
            console.print("[bold]Rationale:[/bold] " + rationale)
            if pr:
                open_pr_with_diff(path, rewritten, rationale)
        else:
            msg = f"[yellow]⏳ LLM rewrite not available: {rationale}[/yellow]"
            console.print(msg)
    except Exception as e:
        logger.exception("Exception during harden: %s", e)
        console.print(f"[bold red]❌ Unexpected error: {e}[/bold red]")


if __name__ == '__main__':
    main()
