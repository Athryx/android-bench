from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn

from android_bench.web.models import RunDetail, TreeResponse, WebConfigResponse
from android_bench.web.service import (
    get_kagent_web_host,
    load_run_detail,
    scan_results_tree,
)
from android_bench.web.static_html import HTML_CONTENT

logger = logging.getLogger(__name__)


def create_app(results_dir: Path) -> FastAPI:
    """Create FastAPI application for android-bench results viewer."""
    resolved_results = results_dir.resolve()
    app = FastAPI(title="android-bench Results Viewer")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse(content=HTML_CONTENT)

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

    return app


def run_server(results_dir: Path, host: str = "127.0.0.1", port: int = 8080) -> None:
    """Run the web viewer server via uvicorn."""
    app = create_app(results_dir)
    print(f"Starting android-bench web viewer on http://{host}:{port} monitoring {results_dir}")
    uvicorn.run(app, host=host, port=port, log_level="info")
