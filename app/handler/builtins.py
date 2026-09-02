# app/handlers/builtins.py

"""Built-in task handlers.

Available workloads:
- sleep: random 200-800 ms sleep with ~30% simulated failure.
- http_fetch: bounded HTTP GET.
- hash: CPU-bound repeated SHA-256.
"""

from __future__ import annotations

import asyncio
import hashlib
import random
import time
from typing import Any

import httpx

from app.model import Task
from app.handler.registry import Result


def _payload(task: Task) -> dict[str, Any]:
    """Return the task payload as a dictionary."""
    return task.payload if isinstance(task.payload, dict) else {}


# --- sleep 
async def sleep(task: Task) -> Result:
    """sleep for 200-800 ms and randomly fail ~30% of the time."""

    payload = _payload(task)

    duration_ms = int(payload.get("duration_ms", 0) or 0)
    fail_rate = float(payload.get("fail_rate", 0.3) or 0.3)

    if duration_ms <= 0:
        duration_ms = random.randint(200,800)
    
    await asyncio.sleep(duration_ms/1000)

    if random.random() < fail_rate:
        raise RuntimeError(f"simulated failure for task {task.id}")
    
    return Result(detail=f"slept {duration_ms}ms")


# --- http_fetch ------------------------------------------------------------
# A dedicated client bounds each fetch (avoids an unbounded default timeout).
__http_client = httpx.AsyncClient(timeout=10.0)


async def http_fetch(task: Task) -> Result:
    """Perform an HTTP GET and fail for non-2xx responses."""
    payload = _payload(task)
    url = payload.get("url")

    if not url:
        raise ValueError("http_fetch: payload.url is required")

    start = time.perf_counter()

    response = await __http_client.get(url)
    latency_ms = (time.perf_counter() - start) * 1000

    if not 200 <= response.status_code < 300:
        raise RuntimeError(
            f"http_fetch: {url} returned "
            f"{response.status_code} in {latency_ms:.0f}ms"
        )

    return Result(detail=f"{response.status_code} in {latency_ms:.0}ms")


# --- hash
async def hash_task(task: Task) -> Result:
    """
    hash_task is a CPU-bound workload: it iterates SHA-256 over the input a configurable number of rounds. 
    Useful for load-testing worker throughput and showing CPU-bound vs IO-bound task behavior.
    Yields every 4096 rounds so the event loop stays responsive and cancellation can be delivered.
    """
    payload = _payload(task)

    rounds = int(payload.get("rounds", 100000) or 100000)
    digest = str(payload.get("input", "")).encode()

    for i in range(rounds):
        if i%4096 == 0:
            await asyncio.sleep(0)
        
        digest = hashlib.sha256(digest).digest()
    
    return Result(detail=f"{rounds} rounds -> {digest.hex()[:16]}")
