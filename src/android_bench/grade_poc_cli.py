"""Standalone CLI for creating and grading a single PoC."""

from pathlib import Path

import typer
from dotenv import load_dotenv

from android_bench.grade_poc import create_poc_template, run_grade_poc
from android_bench.models import Capability

app = typer.Typer(no_args_is_help=True, help="Create or grade one Android capability PoC.")


@app.callback()
def callback() -> None:
    load_dotenv()


@app.command("run")
def run(
    adb: str = typer.Option(..., "--adb", help="Existing Cuttlefish ADB address (host:port)."),
    capability: Capability = typer.Option(..., "--capability", help="Capability to grade."),
    poc: Path = typer.Option(
        ..., "--poc", exists=True, dir_okay=False, resolve_path=True,
        help="Local executable PoC; grade-poc.toml beside it specifies the target package.",
    ),
) -> None:
    """Grade one PoC locally. Requires root adbd; clears target/grader app data."""
    try:
        result = run_grade_poc(adb, capability, poc)
    except (OSError, ValueError, RuntimeError, TimeoutError) as error:
        typer.echo(f"Grading error: {error}", err=True)
        raise typer.Exit(code=2) from error
    typer.echo(result.model_dump_json(indent=2))
    raise typer.Exit(code=0 if result.passed else 1)


@app.command("template")
def template(
    capability: Capability = typer.Option(..., "--capability", help="Capability to demonstrate."),
    file_path: Path = typer.Argument(..., resolve_path=True, help="Path for the executable PoC."),
) -> None:
    """Create a capability PoC template and adjacent grade-poc.toml if needed."""
    try:
        poc, config, created_config = create_poc_template(capability, file_path)
    except (OSError, ValueError) as error:
        typer.echo(f"Template error: {error}", err=True)
        raise typer.Exit(code=2) from error
    typer.echo(f"Created PoC template: {poc}")
    if created_config:
        typer.echo(f"Set the target package in {config} before running the grader.")


def main() -> None:
    app()
