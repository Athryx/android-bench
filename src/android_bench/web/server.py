from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import HTMLResponse
import uvicorn

from android_bench.web.models import NotesUpdate, RunDetail, TreeResponse, WebConfigResponse
from android_bench.web.service import (
    get_kagent_web_host,
    is_run_dir,
    load_run_detail,
    scan_results_tree,
)
from android_bench.web.static_html import HTML_CONTENT

logger = logging.getLogger(__name__)

STATIC_DIR = (Path(__file__).parent / "static").resolve()


def create_app(results_dir: Path) -> FastAPI:
    """Create FastAPI application for android-bench results viewer."""
    resolved_results = results_dir.resolve()
    app = FastAPI(title="android-bench Results Viewer")

    @app.get("/", response_class=HTMLResponse)
    @app.get("/runs/{run_path:path}", response_class=HTMLResponse)
    async def index(run_path: str = "") -> HTMLResponse:
        return HTMLResponse(content=HTML_CONTENT)

    @app.get("/static/{filename}")
    def get_static_file(filename: str) -> Response:
        file_path = (STATIC_DIR / filename).resolve()
        if not file_path.is_relative_to(STATIC_DIR) or not file_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        content_type = "application/javascript" if filename.endswith(".js") else "text/plain"
        return Response(
            content=file_path.read_bytes(),
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    @app.get("/api/config", response_model=WebConfigResponse)
    def get_config() -> WebConfigResponse:
        return WebConfigResponse(
            results_dir=str(resolved_results),
            kagent_web_host=get_kagent_web_host(),
        )

    @app.get("/api/tree", response_model=TreeResponse)
    def get_tree() -> TreeResponse:
        items = scan_results_tree(resolved_results)
        return TreeResponse(root_path=str(resolved_results), items=items)

    @app.get("/api/runs/{run_path:path}", response_model=RunDetail)
    def get_run(run_path: str) -> RunDetail:
        try:
            return load_run_detail(resolved_results, run_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/runs/{run_path:path}/notes", response_model=NotesUpdate)
    def put_run_notes(run_path: str, update: NotesUpdate) -> NotesUpdate:
        run_dir = (resolved_results / run_path).resolve()
        if not run_dir.is_relative_to(resolved_results):
            raise HTTPException(status_code=400, detail="Run path is outside results directory")
        if not is_run_dir(run_dir):
            raise HTTPException(status_code=404, detail="Run directory not found")

        notes_file = run_dir / "NOTES.md"
        if notes_file.is_symlink():
            raise HTTPException(status_code=400, detail="NOTES.md cannot be a symbolic link")
        try:
            notes_file.write_text(update.notes, encoding="utf-8")
        except OSError as exc:
            logger.exception("Could not save notes for %s", run_dir)
            raise HTTPException(status_code=500, detail="Could not save notes") from exc
        return update

    return app


def run_server(results_dir: Path, host: str = "127.0.0.1", port: int = 8080) -> None:
    """Run the web viewer server via uvicorn."""
    app = create_app(results_dir)
    print(f"Starting android-bench web viewer on http://{host}:{port} monitoring {results_dir}")
    uvicorn.run(app, host=host, port=port, log_level="info")
