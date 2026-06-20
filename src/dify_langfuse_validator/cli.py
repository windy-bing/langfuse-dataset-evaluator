from __future__ import annotations

import sys
from datetime import datetime

import typer
from dotenv import load_dotenv

from dify_langfuse_validator.config import PROJECT_ROOT, Settings
from dify_langfuse_validator.langfuse_runner import DatasetFetchError, LangfuseDatasetRunner

app = typer.Typer(help="Run Dify answers against a Langfuse dataset.")


def _echo(message: object) -> None:
    text = str(message)
    encoding = sys.stdout.encoding or "utf-8"
    typer.echo(text.encode(encoding, errors="replace").decode(encoding))


@app.callback()
def main() -> None:
    """Dify + Langfuse dataset validation commands."""


@app.command()
def run(
    dataset: str = typer.Option(..., "--dataset", "-d", help="Langfuse dataset name."),
    run_name: str | None = typer.Option(None, "--run-name", "-r", help="Langfuse dataset run name."),
    threshold: float = typer.Option(0.8, "--threshold", "-t", min=0.0, max=1.0, help="Similarity pass threshold."),
    limit: int | None = typer.Option(None, "--limit", "-l", min=1, help="Maximum dataset items to run."),
    max_concurrency: int = typer.Option(3, "--max-concurrency", "-c", min=1, help="Maximum parallel Dify calls."),
) -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    settings = Settings()
    effective_run_name = run_name or f"dify-validation-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    runner = LangfuseDatasetRunner(settings)
    try:
        result = runner.run_dataset(dataset, effective_run_name, threshold, limit, max_concurrency)
    except DatasetFetchError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    _echo(f"Run: {effective_run_name}")
    _echo(f"Dataset: {dataset}")
    formatter = getattr(result, "format", None)
    if callable(formatter):
        _echo(formatter())
    else:
        _echo(result)


if __name__ == "__main__":
    app()
