"""WebSocket endpoint for real-time job status updates.

Clients connect to /ws/status/{job_id} and receive JSON status messages
pushed by the pipeline thread whenever progress changes.

Falls back gracefully — if the client disconnects, messages are simply dropped.
"""

import asyncio
import json
import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from datetime import datetime, timezone

logger = structlog.get_logger()

ws_router = APIRouter()

# Registry: job_id -> set of connected WebSocket clients
_ws_clients: dict[str, set[WebSocket]] = {}
_ws_lock = asyncio.Lock()


async def register_client(job_id: str, ws: WebSocket):
    """Register a WebSocket client for a job."""
    async with _ws_lock:
        if job_id not in _ws_clients:
            _ws_clients[job_id] = set()
        _ws_clients[job_id].add(ws)
    logger.debug("WS client registered", job_id=job_id, clients=len(_ws_clients.get(job_id, set())))


async def unregister_client(job_id: str, ws: WebSocket):
    """Unregister a WebSocket client."""
    async with _ws_lock:
        if job_id in _ws_clients:
            _ws_clients[job_id].discard(ws)
            if not _ws_clients[job_id]:
                del _ws_clients[job_id]
    logger.debug("WS client unregistered", job_id=job_id)


async def broadcast_status(job_id: str, data: dict):
    """Push a status update to all connected WebSocket clients for a job.

    Called from the pipeline thread via an async bridge.
    Silently drops messages if no clients are connected.
    """
    async with _ws_lock:
        clients = list(_ws_clients.get(job_id, set()))

    if not clients:
        return

    message = json.dumps(data)
    dead = []
    for ws in clients:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)

    # Cleanup dead connections
    if dead:
        async with _ws_lock:
            for ws in dead:
                if job_id in _ws_clients:
                    _ws_clients[job_id].discard(ws)


_main_event_loop: asyncio.AbstractEventLoop | None = None


def set_main_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Store the main event loop reference at app startup for use by pipeline threads."""
    global _main_event_loop
    _main_event_loop = loop


def push_status_sync(job_id: str, data: dict):
    """Thread-safe bridge: schedule broadcast_status onto the running event loop.

    Called from pipeline threads (sync context) to push updates to WS clients.
    """
    loop = _main_event_loop
    if loop is not None and loop.is_running():
        asyncio.run_coroutine_threadsafe(broadcast_status(job_id, data), loop)
    else:
        pass


@ws_router.websocket("/ws/status/{job_id}")
async def ws_job_status(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job status.

    Protocol:
    1. Client connects to /ws/status/{job_id}
    2. Server sends current status immediately
    3. Server pushes updates as they happen
    4. Server sends final status (complete/failed) and closes
    5. Client can send "ping" to keep alive; server responds "pong"
    """
    await websocket.accept()
    await register_client(job_id, websocket)
    logger.info("WS connection opened", job_id=job_id)

    try:
        # Send current status immediately
        from api.routes import _get_job, _in_memory_jobs
        current = _get_job(job_id) or _in_memory_jobs.get(job_id)
        if current:
            await websocket.send_text(json.dumps(current))

            # If already terminal, close after sending
            if current.get("status") in ("complete", "failed"):
                await websocket.close(code=1000, reason="Job already finished")
                return
        else:
            await websocket.send_text(json.dumps({
                "job_id": job_id,
                "status": "unknown",
                "current_step": "Waiting for job to start...",
                "progress": 0,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }))

        # Keep connection alive — listen for client messages (ping/close)
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if msg == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send a heartbeat to detect dead connections
                try:
                    await websocket.send_text(json.dumps({"type": "heartbeat"}))
                except Exception:
                    break
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        logger.debug("WS client disconnected", job_id=job_id)
    except Exception as e:
        logger.warning("WS error", job_id=job_id, error=str(e))
    finally:
        await unregister_client(job_id, websocket)
        logger.info("WS connection closed", job_id=job_id)
