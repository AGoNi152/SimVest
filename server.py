from __future__ import annotations

import argparse
import json
import mimetypes
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .ai_advisor import generate_ai_advice, latest_ai_advice
from .config import ASSET_SCOPE, BASE_CURRENCY, INITIAL_CAPITAL, RISK_POLICY, STATIC_DIR
from .data_pipeline import (
    list_raw_documents,
    list_source_runs,
    load_source_config,
    run_public_data_pipeline,
)
from .db import connect, init_db
from .engine import (
    add_event,
    asset_rows,
    benchmark_rows,
    confirm_decision,
    dashboard_view,
    data_health,
    event_rows,
    latest_report,
    list_reports,
    performance_series,
    portfolio_state,
    reject_decision,
    run_daily_decision,
    stock_detail,
    stock_rows,
)
from .expert_debate import expert_prompts, latest_expert_debate, run_expert_debate
from .reports import ensure_report_exports
from .seed import seed_if_empty
from .universe import sync_market_universe, universe_detail, universe_rows, universe_summary


DATA_SYNC_LOCK = threading.Lock()
EXPERT_DEBATE_LOCK = threading.Lock()


def safe_print(message: str) -> None:
    try:
        print(message)
    except OSError:
        pass


class SimVestHandler(BaseHTTPRequestHandler):
    server_version = "SimVest/0.2"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_common_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            if path.startswith("/api/"):
                self.handle_api_get(path, query)
                return
            self.serve_static(path)
        except Exception as exc:  # pragma: no cover - defensive server boundary
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            payload = self.read_json()
            self.handle_api_post(path, payload)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - defensive server boundary
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def handle_api_get(self, path: str, query: dict[str, list[str]]) -> None:
        if path == "/api/health":
            self.send_json(
                {
                    "status": "ok",
                    "mode": "simulation_only",
                    "real_trading_enabled": False,
                    "base_currency": BASE_CURRENCY,
                    "version": "0.2",
                }
            )
            return
        if path == "/api/config":
            self.send_json(
                {
                    "initial_capital": INITIAL_CAPITAL,
                    "risk_policy": RISK_POLICY,
                    "asset_scope": ASSET_SCOPE,
                }
            )
            return
        if path == "/api/dashboard":
            self.send_json(dashboard_view())
            return
        if path == "/api/data/health":
            self.send_json({"health": data_health()})
            return
        if path == "/api/universe/summary":
            self.send_json({"summary": universe_summary()})
            return
        if path == "/api/universe":
            self.send_json(universe_rows(query))
            return
        if path.startswith("/api/universe/"):
            symbol = unquote(path.removeprefix("/api/universe/"))
            detail = universe_detail(symbol)
            if not detail:
                self.send_json({"error": "Instrument not found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json(detail)
            return
        if path == "/api/data/config":
            self.send_json({"config": load_source_config()})
            return
        if path == "/api/data/runs":
            self.send_json({"runs": list_source_runs()})
            return
        if path == "/api/data/documents":
            self.send_json({"documents": list_raw_documents()})
            return
        if path == "/api/assets":
            asset_class = query.get("class", [None])[0]
            self.send_json({"assets": asset_rows(asset_class)})
            return
        if path == "/api/stocks":
            self.send_json(stock_rows())
            return
        if path.startswith("/api/stocks/"):
            symbol = unquote(path.removeprefix("/api/stocks/"))
            detail = stock_detail(symbol)
            if not detail:
                self.send_json({"error": "Stock not found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json(detail)
            return
        if path == "/api/ai/advice/latest":
            self.send_json({"advice": latest_ai_advice()})
            return
        if path == "/api/expert-debate/prompts":
            self.send_json(expert_prompts())
            return
        if path == "/api/expert-debate/latest":
            self.send_json({"report": latest_expert_debate()})
            return
        if path.startswith("/api/expert-debate/latest/"):
            report = latest_expert_debate()
            if not report:
                self.send_json({"error": "Expert debate report not found"}, HTTPStatus.NOT_FOUND)
                return
            export_type = path.removeprefix("/api/expert-debate/latest/")
            field_by_type = {
                "pdf": "pdf_path",
                "excel": "excel_path",
                "markdown": "markdown_path",
            }
            field = field_by_type.get(export_type)
            if not field or not report.get(field):
                self.send_json({"error": "Export not found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_file(Path(report[field]))
            return
        if path == "/api/benchmarks":
            self.send_json({"benchmarks": benchmark_rows()})
            return
        if path == "/api/events":
            self.send_json({"events": event_rows()})
            return
        if path == "/api/portfolio":
            with connect() as conn:
                state = portfolio_state(conn)
            self.send_json(state)
            return
        if path == "/api/performance":
            self.send_json({"series": performance_series()})
            return
        if path == "/api/reports":
            self.send_json({"reports": list_reports()})
            return
        if path == "/api/reports/latest":
            self.send_json({"report": latest_report()})
            return
        if path.startswith("/api/reports/"):
            parts = path.strip("/").split("/")
            if len(parts) >= 3:
                report_id = parts[2]
                if len(parts) == 3:
                    from .engine import get_report

                    report = get_report(report_id)
                    if not report:
                        self.send_json({"error": "Report not found"}, HTTPStatus.NOT_FOUND)
                        return
                    self.send_json({"report": report})
                    return
                if len(parts) == 4 and parts[3] in {"pdf", "excel"}:
                    paths = ensure_report_exports(report_id)
                    self.send_file(Path(paths[parts[3]]))
                    return
        self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def handle_api_post(self, path: str, payload: dict) -> None:
        if path == "/api/daily/run":
            if payload.get("sync", True):
                sync_result = run_data_sync_once()
                if sync_result.get("status") == "busy":
                    self.send_json(sync_result, HTTPStatus.CONFLICT)
                    return
            report = run_daily_decision()
            ensure_report_exports(report["id"])
            self.send_json({"report": latest_report()})
            return
        if path == "/api/data/sync":
            result = run_data_sync_once()
            if result.get("status") == "busy":
                self.send_json(result, HTTPStatus.CONFLICT)
                return
            self.send_json(result)
            return
        if path == "/api/universe/sync":
            self.send_json(sync_market_universe())
            return
        if path == "/api/ai/advice":
            if payload.get("sync", False):
                sync_result = run_data_sync_once()
                if sync_result.get("status") == "busy":
                    self.send_json(sync_result, HTTPStatus.CONFLICT)
                    return
            self.send_json({"advice": generate_ai_advice()})
            return
        if path == "/api/expert-debate/run":
            if payload.get("sync", False):
                sync_result = run_data_sync_once()
                if sync_result.get("status") == "busy":
                    self.send_json(sync_result, HTTPStatus.CONFLICT)
                    return
            result = run_expert_debate_once()
            if result.get("status") == "busy":
                self.send_json(result, HTTPStatus.CONFLICT)
                return
            self.send_json({"report": result})
            return
        if path == "/api/events":
            event = add_event(payload)
            self.send_json({"event": event}, HTTPStatus.CREATED)
            return
        if path.startswith("/api/decisions/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[3] == "confirm":
                self.send_json(confirm_decision(parts[2]))
                return
            if len(parts) == 4 and parts[3] == "reject":
                self.send_json(reject_decision(parts[2]))
                return
        self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON payload") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON payload must be an object")
        return payload

    def serve_static(self, path: str) -> None:
        if path in {"", "/"}:
            path = "/index.html"
        safe_part = unquote(path).lstrip("/")
        target = (STATIC_DIR / safe_part).resolve()
        root = STATIC_DIR.resolve()
        try:
            target.relative_to(root)
        except ValueError:
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        if not target.exists() or target.is_dir():
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        self.send_file(target)

    def send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_common_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_json({"error": "File not found"}, HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        mime_type, _ = mimetypes.guess_type(path.name)
        if path.suffix == ".xlsx":
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif path.suffix == ".pdf":
            mime_type = "application/pdf"
        self.send_response(HTTPStatus.OK)
        self.send_common_headers()
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'inline; filename="{path.name}"')
        self.end_headers()
        self.wfile.write(body)

    def send_common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")


def prepare_app() -> None:
    init_db()
    seed_if_empty()
    if latest_report() is None:
        report = run_daily_decision()
        ensure_report_exports(report["id"])


def run_data_sync_once() -> dict:
    if not DATA_SYNC_LOCK.acquire(blocking=False):
        return {
            "status": "busy",
            "message": "数据同步正在进行，请稍后刷新。",
            "message_en": "Data sync is already running. Please refresh later.",
        }
    try:
        return run_public_data_pipeline(generate_snapshot=True)
    finally:
        DATA_SYNC_LOCK.release()


def run_expert_debate_once() -> dict:
    if not EXPERT_DEBATE_LOCK.acquire(blocking=False):
        return {
            "status": "busy",
            "message": "专家辩论报告正在生成，请稍后刷新。",
            "message_en": "Expert debate report is already running. Please refresh later.",
        }
    try:
        return run_expert_debate()
    finally:
        EXPERT_DEBATE_LOCK.release()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SimVest local server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()

    prepare_app()
    server = ThreadingHTTPServer((args.host, args.port), SimVestHandler)
    safe_print(f"SimVest running at http://{args.host}:{args.port}")
    safe_print("Simulation only. No real broker order can be sent.")
    server.serve_forever()


if __name__ == "__main__":
    main()
