"""
Sentry FastAPI application.

Exposes a single WebSocket endpoint at /ws that:
  1. Accepts a JSON start message: {repo_url, test_cmd, runtime}
  2. Runs SentryOrchestrator in a thread (it is fully synchronous)
  3. Streams each emitted event as a JSON string back to the client
  4. Sends a terminal "done" frame and closes cleanly when the pipeline finishes

Start with:
    uvicorn backend.main:app --reload
"""

import asyncio
import json
import logging
import sys
import os
import concurrent.futures
import time

# Make sure 'backend/' is importable as the module root when run via uvicorn
# from the repo root (uvicorn backend.main:app).
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from orchestrator.state_machine import SentryOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("sentry.main")

app = FastAPI(title="Sentry API")

# Allow the Next.js dev server (port 3000) to connect.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    """
    Single-session WebSocket endpoint.

    Protocol:
      Client → Server (once):  JSON string {"repo_url": str, "test_cmd": str, "runtime": str}
      Server → Client (many):  JSON strings, each a canonical orchestrator event
                                {event_type, state, timestamp, message, data}
      Server → Client (final): {"event_type": "done", "state": "DONE",
                                 "timestamp": "...", "message": "Pipeline complete.", "data": {}}
      Server closes the connection after the final frame.
    """
    await websocket.accept()
    logger.info("WebSocket client connected")

    try:
        raw = await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("Client disconnected before sending start message")
        return

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        await websocket.send_text(json.dumps({
            "event_type": "error",
            "state": "ERROR",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "message": f"Invalid JSON in start message: {exc}",
            "data": {},
        }))
        await websocket.close()
        return

    repo_url = payload.get("repo_url", "").strip()
    test_cmd = payload.get("test_cmd", "").strip()
    runtime = payload.get("runtime", "python").strip()

    if not repo_url or not test_cmd:
        await websocket.send_text(json.dumps({
            "event_type": "error",
            "state": "ERROR",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "message": "Start message must include non-empty 'repo_url' and 'test_cmd'.",
            "data": {},
        }))
        await websocket.close()
        return

    logger.info("Starting pipeline: repo=%s test_cmd=%s runtime=%s", repo_url, test_cmd, runtime)

    loop = asyncio.get_event_loop()

    def emit(event: dict) -> None:
        """Thread-safe: schedule send on the event loop from the worker thread."""
        future = asyncio.run_coroutine_threadsafe(
            websocket.send_text(json.dumps(event)), loop
        )
        # Block the worker thread briefly to propagate send errors early.
        try:
            future.result(timeout=10)
        except Exception as exc:
            logger.warning("Failed to send event to client: %s", exc)

    orchestrator = SentryOrchestrator(
        max_attempts=3,
        emit_callback=emit,
    )

    try:
        await loop.run_in_executor(
            _executor,
            lambda: orchestrator.run(
                repo_url=repo_url,
                test_cmd=test_cmd,
                runtime=runtime,
            ),
        )
    except Exception as exc:
        logger.exception("Orchestrator raised an unhandled exception")
        try:
            await websocket.send_text(json.dumps({
                "event_type": "error",
                "state": "ERROR",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "message": f"Orchestrator error: {exc}",
                "data": {"error_type": type(exc).__name__},
            }))
        except Exception:
            pass

    # Terminal "done" frame so the client knows the stream has ended.
    try:
        await websocket.send_text(json.dumps({
            "event_type": "done",
            "state": "DONE",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "message": "Pipeline complete.",
            "data": {},
        }))
        await websocket.close()
    except Exception:
        pass

    logger.info("WebSocket connection closed")
