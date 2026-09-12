# Distributed_task_queue_system
# Distributed Task Queue System

A Redis-backed distributed task queue built with Python, FastAPI, and asyncio.

The core building blocks of  distributed task queue:

* Task submission and persistence
* Priority-based queues
* Delayed task scheduling
* Atomic Redis/Lua operations
* Worker execution
* Visibility timeouts and leases
* Retries with backoff
* Dead-letter queues
* Task redrive
* Metrics
* Cluster membership and worker heartbeats

---

## Current Architecture

At a high level:

```text
                   ┌──────────────────┐
                   │   FastAPI API     │
                   │                  │
                   │ Submit / Get     │
                   │ Metrics / DLQ    │
                   └────────┬─────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │     Redis     │
                    │               │
                    │ Task Records  │
                    │ Ready Queue   │
                    │ Delayed Queue │
                    │ Processing    │
                    │ Dead Letter   │
                    │ Metrics       │
                    └───────┬───────┘
                            │
                 ┌──────────┴──────────┐
                 ▼                     ▼
          ┌──────────────┐      ┌──────────────┐
          │   Worker 1   │      │   Worker 2   │
          │              │      │              │
          │ Executor     │      │ Executor     │
          │ Pool         │      │ Pool         │
          └──────────────┘      └──────────────┘
```

Redis is the central coordination layer between API processes, workers, schedulers, and task state.

---


# Project Structure

```text
app/
├── api/
│   ├── dependencies.py
│   ├── middleware.py
│   ├── router.py
│   ├── routes/
│   │   ├── task.py
│   │   └── metrics.py
│   └── schema.py
│
├── broker/
│   ├── broker.py
│   └── scripts/
│       ├── ack.lua
│       ├── dequeue.lua
│       ├── extend.lua
│       └── nack.lua
│
├── core/
│   ├── config.py
│   └── logging.py
│
├── handler/
│   ├── builtins.py
│   └── registry.py
│
├── model/
│   └── task.py
│
├── queue/
│   ├── queue.py
│   ├── delayed.py
│   └── scripts/
│       ├── enqueue.lua
│       ├── promote.lua
│       └── retry.lua
│
├── run_worker.py
├── main.py
└── container.py
```

---

## Tech Stack

* **Python:** 3.14+
* **FastAPI:** HTTP API
* **Uvicorn:** ASGI server
* **Redis:** queue, task state, leases, delayed scheduling, metrics
* **asyncio:** asynchronous workers and scheduling
* **httpx:** HTTP task handler
* **Pydantic Settings:** configuration
* **uv:** dependency and environment management

Project dependencies are defined in `pyproject.toml`.

---

# Getting Started

## 1. Clone the repository

```bash
git clone https://github.com/vikash1807/Distributed_task_queue_system.git
cd Distributed_task_queue_system
```

## 2. Install Python

The project requires Python **3.14 or newer**.

Check your version:

```bash
python --version
```

The repository also contains `.python-version` for the project Python version.

---

## 3. Install uv

Install `uv` if it is not already installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify:

```bash
uv --version
```

---

## 4. Install dependencies

```bash
uv sync
```

This creates/uses the project's virtual environment and installs the dependencies from `pyproject.toml` and `uv.lock`.

---

# Redis Setup

Redis is required for the application.

The default configuration expects:

```text
localhost:6379
```

Start Redis locally.

For example, using Docker:

```bash
docker run --name taskqueue-redis -p 6379:6379 -d redis
```

Verify the connection:

```bash
docker exec -it taskqueue-redis redis-cli
PING
```

Expected:

```text
PONG
```

---

# Configuration

Configuration is loaded from environment variables. Refer `.env.example`.

The current defaults are:

| Variable                |          Default | Description                    |
| ----------------------- | ---------------: | ------------------------------ |
| `REDIS_ADDR`            | `localhost:6379` | Redis address                  |
| `REDIS_PASSWORD`        |            empty | Redis password                 |
| `SERVER_PORT`           |           `8080` | API server port                |
| `METRICS_PORT`          |           `9100` | Metrics port                   |
| `WORKER_COUNT`          |              `5` | Workers per worker process     |
| `POLL_INTERVAL_MS`      |            `500` | Worker polling interval        |
| `DRAIN_TIMEOUT_MS`      |           `5000` | Shutdown drain timeout         |
| `VISIBILITY_TIMEOUT_MS` |          `30000` | Task lease/visibility timeout  |
| `SIGNAL_BLOCK_MS`       |           `1000` | Redis signal blocking interval |
| `SIGNAL_CAP`            |           `1024` | Signal capacity                |

These defaults and validations are defined in `app/core/config.py`.

You can provide configuration through environment variables:
`.env` file if preferred.

---

# Running the Application

The project has two main processes:

1. API server
2. Worker process

## Start the API server

```bash
uv run python -m app.main
```

The API listens on:

```text
http://localhost:8080
```

The API application initializes Redis and starts the delayed scheduler during its lifespan.

---

## Start a worker

In another terminal:

```bash
uv run python -m app.run_worker
```

The worker process:

1. Loads configuration.
2. Connects to Redis.
3. Builds the task store and queue.
4. Starts the delayed scheduler.
5. Creates the broker and executor.
6. Starts the worker pool.
7. Waits until shutdown.
8. Gracefully stops the worker pool.

You can run multiple worker processes to simulate a distributed cluster by increasing `worker_count` in enironment variables.

---

# API

Base URL:

```text
http://localhost:8080
```

## Submit a task

```http
POST /api/tasks
```

Example:

```bash
curl -X POST http://localhost:8080/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "type": "sleep",
    "payload": {
      "duration_ms": 800
    },
    "priority": 5,
    "delay": 0,
    "max_retries": 3
  }'
```

The API returns the created task.

---

## Get a task

```http
GET /api/tasks/{task_id}
```

Example:

```bash
curl http://localhost:8080/api/tasks/<task_id>
```

---

## Get failed tasks

```http
GET /api/tasks/failed
```

Optional pagination:

```bash
curl "http://localhost:8080/api/tasks/failed?offset=0&limit=20"
```

---

## Redrive failed tasks

```http
GET /api/tasks/failed/redrive
```

This moves failed/dead-lettered tasks back into the normal processing flow.

---

## Get metrics

```http
GET /api/metrics
```

Example:

```bash
curl http://localhost:8080/api/metrics
```

Enhanced metrics:

```http
GET /api/metrics/enhanced
```

---

# Built-in Task Handlers

The current worker includes three built-in task types.

## `sleep`

Sleeps for a configurable duration.

```json
{
  "type": "sleep",
  "payload": {
    "duration_ms": 800
  }
}
```

A `fail_rate` can also be provided for testing retries/failures:

```json
{
  "type": "sleep",
  "payload": {
    "duration_ms": 800,
    "fail_rate": 0.3
  }
}
```

---

## `http_fetch`

Performs an HTTP GET request.

```json
{
  "type": "http_fetch",
  "payload": {
    "url": "https://example.com"
  }
}
```

The request uses a bounded HTTP timeout.

---

## `hash`

Performs repeated SHA-256 hashing.

```json
{
  "type": "hash",
  "payload": {
    "input": "hello",
    "rounds": 100000
  }
}
```

This is useful for testing CPU-heavy workloads.

The built-in handlers are implemented in `app/handler/builtins.py`.

---

# Task Lifecycle

A task generally moves through the following lifecycle:

```text
                submit
                   │
                   ▼
              ┌─────────┐
              │  Saved  │
              └────┬────┘
                   │
                   ▼
             ┌───────────┐
             │   Ready   │
             └─────┬─────┘
                   │
                   ▼
             ┌───────────┐
             │ Processing│
             └─────┬─────┘
                   │
          ┌────────┴────────┐
          │                 │
       success            failure
          │                 │
          ▼                 ▼
      completed          retry
                            │
                     ┌──────┴──────┐
                     │             │
                  retry        max retries
                     │             │
                     ▼             ▼
                  ready        dead-letter
```

Delayed tasks additionally pass through the delayed queue before becoming ready.

---

# Redis Data Model

Redis is used for both task storage and queue coordination.

Important structures include:

```text
taskqueue:task:{id}
taskqueue:ready
taskqueue:delayed
taskqueue:processing
taskqueue:deadletter
```

The exact Redis operations are intentionally implemented inside dedicated store/queue/broker components.

Lua scripts are used where multiple Redis operations must happen atomically.

Examples include:

```text
enqueue.lua
promote.lua
retry.lua
dequeue.lua
ack.lua
nack.lua
extend.lua
```

This prevents race conditions between multiple worker processes.

---

# Delayed Tasks

Tasks can be submitted with a delay:

```json
{
  "type": "sleep",
  "payload": {
    "duration_ms": 500
  },
  "priority": 5,
  "delay": 20,
  "max_retries": 3
}
```

The delayed scheduler monitors the delayed queue and promotes tasks to the ready queue when their scheduled time is reached.

The scheduler runs in the API process and worker process where configured.

---

# Retries

Failed tasks can be retried according to their `max_retries` configuration.

The retry flow uses Redis atomically to prevent inconsistent task state.

Conceptually:

```text
Processing
    │
    │ failure
    ▼
Retry decision
    │
    ├── retries remaining ──► delayed/ready
    │
    └── retries exhausted ─► dead-letter
```

Retry delays use backoff to avoid immediately retrying a repeatedly failing task.

---

# Visibility Timeout and Leases

When a worker claims a task, the task receives a lease.

The visibility timeout prevents a task from remaining permanently stuck if a worker disappears while processing it.

Workers can extend the lease while required and acknowledge successful completion.

The broker uses atomic Redis/Lua operations for:

* dequeue/claim
* acknowledge
* negative acknowledgement
* lease extension

This is an important part of the distributed-worker safety model.

---

# Dead-Letter Queue

Tasks that exhaust their retry policy are moved to the dead-letter queue.

Dead-lettered tasks can be inspected through:

```http
GET /api/tasks/failed
```

They can also be redriven:

```http
GET /api/tasks/failed/redrive
```

This allows failed work to be returned to the normal queue after the underlying problem has been addressed.

---

# Metrics

The system exposes task processing metrics through:

```http
GET /api/metrics
```

and:

```http
GET /api/metrics/enhanced
```

Metrics are stored in Redis and updated as tasks move through different lifecycle states.

---


# Useful Redis Commands

Check Redis:

```redis-cli
ping
```

Inspect the ready queue:

```redis-cli
ZRANGE taskqueue:ready 0 -1 WITHSCORES
```

Inspect delayed tasks:

```redis-cli
ZRANGE taskqueue:delayed 0 -1 WITHSCORES
```

Inspect dead-letter tasks:

```redis-cli
ZRANGE taskqueue:deadletter 0 -1 WITHSCORES
```

Inspect a task record:

```redis-cli
HGETALL taskqueue:task:<task_id>
```

Inspect processing tasks:

```redis-cli
SMEMBERS taskqueue:processing
```

---

# Development Workflow

The project is intentionally being built incrementally.

Each development stage introduces another distributed-systems concept while keeping the implementation testable.

Current development areas include:

```text
Task persistence
      ↓
Priority queue
      ↓
Atomic dequeue + leasing
      ↓
Worker execution
      ↓
Visibility timeout
      ↓
Retries + backoff
      ↓
Dead-letter queue
      ↓
Delayed scheduling
      ↓
Metrics
      ↓
Cluster membership + heartbeats
      ↓
Reaper / stale-node cleanup
```

The next major step is cluster membership and worker heartbeats so the system can identify live worker nodes and expose their runtime state.

---

# Design Principles

The project focuses on a few important distributed-systems principles:

### Atomicity

Operations that modify multiple pieces of Redis state should happen atomically, preferably through Lua scripts.

### Explicit task state

Task state is persisted independently from queue membership so tasks can be inspected and recovered.

### Lease-based processing

Workers do not own tasks forever. Processing ownership is represented through a lease with a visibility timeout.

### Failure recovery

Worker crashes should not permanently lose tasks.

### Separation of responsibilities

API, queue, broker, worker, persistence, scheduling, and task handlers have separate responsibilities.

---

# Project Status

This project is an ongoing implementation and focused on building a distributed task queue from the ground up.

Implemented areas currently include:

* Task persistence
* Task submission API
* Priority queue
* Delayed scheduling
* Atomic Redis/Lua queue operations
* Worker pool
* Task execution
* Task leases
* Lease extension
* Retries
* Backoff
* Dead-letter queue
* Failed-task inspection
* Failed-task redrive
* Metrics

Cluster membership and heartbeat support is the next development stage.

---

# License

This project is currently a personal development/learning project.
