import click
from rich.console import Console
from rich.table import Table
import os

from slimcraft.scanner import analyze_dockerfile

console = Console()

@click.group()
def main():
    """🛡️ slimcraft: Agentic container hardening that you can actually trust."""
    pass

@main.command()
@click.argument('dockerfile_path', type=click.Path(exists=True, dir_okay=False))
def scan(dockerfile_path):
    """Scan a Dockerfile for bloat and vulnerabilities."""
    console.print(f"[bold blue]🔍 Scanning {dockerfile_path}...[/bold blue]")
    
    with console.status("Analyzing AST and Layers..."):
        results = analyze_dockerfile(dockerfile_path)
    
    if "error" in results:
        console.print(f"[bold red]❌ Error: {results['error']}[/bold red]")
        return
        
    console.print(f"[bold green]✅ Scan complete![/bold green]\n")
    
    # Print Metrics
    metrics_table = Table(title="📊 Image Metrics")
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Value", style="magenta")
    
    metrics_table.add_row("Base Image", results.get("base_image", "Unknown"))
    metrics_table.add_row("Multi-stage", "Yes" if results.get("is_multi_stage") else "[red]No[/red]")
    
    if results.get("size_mb") is not None:
        metrics_table.add_row("Image Size", f"{results['size_mb']:.2f} MB")
    
    console.print(metrics_table)
    console.print()
    
    # Print Warnings
    warnings = results.get("warnings", [])
    if warnings:
        warnings_table = Table(title="⚠️ Anti-Patterns Detected", show_lines=True)
        warnings_table.add_column("Severity", style="red", justify="center")
        warnings_table.add_column("Issue", style="yellow")
        warnings_table.add_column("Recommendation", style="green")
        
        for w in warnings:
            warnings_table.add_row(w.get("severity", "Warning"), w["issue"], w["recommendation"])
            
        console.print(warnings_table)
    else:
        console.print("[bold green]🎉 No obvious anti-patterns detected![/bold green]")
        
@main.command()
@click.argument('dockerfile_path', type=click.Path(exists=True, dir_okay=False))
@click.option('--rewrite', is_flag=True, help="Use LLM to rewrite the Dockerfile")
@click.option('--pr', is_flag=True, help="Open a Pull Request with the rewrite")
def harden(dockerfile_path, rewrite, pr):
    """Harden a Dockerfile using agentic rewriting."""
    console.print("[bold yellow]🚧 The 'harden' command is coming in v0.2![/bold yellow]")
    console.print("Currently only the 'scan' deterministic core is available.")

if __name__ == '__main__':
    main()
