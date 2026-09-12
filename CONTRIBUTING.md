# Contributing

Thanks for contributing to the Distributed Task Queue System.

This project is being built incrementally, with a strong focus on understanding distributed-systems concepts and keeping the implementation modular, testable, and production-oriented.

Before making changes, please read the project [README](README.md) to understand the architecture and current functionality.

---

## Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/vikash1807/Distributed_task_queue_system.git
cd Distributed_task_queue_system
```

### 2. Install dependencies

The project uses `uv`.

```bash
uv sync
```

### 3. Start Redis

Redis is required for running the application.
---

# Development Workflow

Create a branch for your work : follow belw defined conventions

```bash
git checkout -b feat/<short-description>
```

Examples:

```bash
git checkout -b feat/node-heartbeat
git checkout -b fix/retry-lease
git checkout -b test/task-store
```

Keep changes focused on one feature, bug, or improvement.

---

# Before Submitting Changes

Run the following checks before opening a pull request.

## 1. Run Ruff linting

```bash
uv run ruff check <file_path>
```
to fix linting

```bash
uv run ruff check <file_path> --fix
```

The project currently enables checks including:

* pycodestyle
* Pyflakes
* import sorting
* bugbear
* comprehensions
* pyupgrade
* unused arguments
* simplify

See `ruff.toml` for the complete configuration.

## 2. Run Ruff formatter

```bash
uv run ruff format <file_path>
```

Check formatting without modifying files:

```bash
uv run ruff format <file_path> --check .
```
---

# Code Guidelines

## Keep Responsibilities Separate

Follow the existing project structure.

For example:

* `app/api/` — HTTP/API layer
* `app/queue/` — queue and scheduling logic
* `app/broker/` — task claiming, leases, acknowledgements
* `app/store/` — Redis persistence
* `app/worker/` — worker execution
* `app/handler/` — task handlers
* `app/model/` — domain models
* `app/core/` — configuration and shared infrastructure

Avoid putting business logic directly into API routes.

---

## Prefer Async Code

The application is built around `asyncio`.

Use asynchronous APIs for Redis, HTTP, task execution, and other I/O-bound operations.

Avoid blocking the event loop with synchronous I/O.

---

## Preserve Atomicity

When an operation modifies multiple pieces of shared Redis state, consider whether it needs to be atomic.

For example, task claiming may involve:

```text
ready queue
    ↓
processing state
    ↓
lease
```

Operations that must happen together should use the existing Redis/Lua approach rather than separate non-atomic commands.

---

## Handle Failures Explicitly

Distributed systems must assume that processes, network connections, and tasks can fail.

When adding functionality, consider:

* worker crashes
* Redis failures
* task retries
* expired leases
* cancellation
* partial failures

Do not silently swallow exceptions.

Use logging where failures require operational visibility.

---

# Redis Changes

If you introduce a new Redis key, set, sorted set, hash, or other structure:

1. Document its purpose.
2. Follow the existing `taskqueue:*` naming convention.
3. Consider its lifecycle.
4. Consider what happens when the process crashes.
5. Consider whether the operation needs atomicity.

Example naming style:

```text
taskqueue:task:{id}
taskqueue:ready
taskqueue:processing
taskqueue:deadletter
```

---

# Lua Scripts

Lua scripts are used when Redis operations need server-side atomicity.

If modifying or adding a Lua script:

* Keep the script focused.
* Clearly document `KEYS` and `ARGV`.
* Keep key ownership explicit.
* Consider retry and failure behavior.

Avoid moving atomic operations back into multiple client-side Redis commands without a strong reason.

---

# API Changes

When adding or changing an API endpoint:

* Follow the existing router structure.
* Validate request data.
* Return appropriate HTTP status codes.
* Use consistent error responses.
* Keep service/business logic outside the route handler.

Example existing API structure:

```text
/api/tasks
/api/tasks/{task_id}
/api/tasks/failed
/api/tasks/failed/redrive
/api/metrics
/api/metrics/enhanced
```

---

# Commit Messages

Keep commit messages short and descriptive.

Examples:

```text
feat: add worker heartbeat
fix: handle expired task lease
test: add retry queue coverage
refactor: simplify broker dependencies
docs: update setup instructions
chore: configure ruff
```

Prefer one logical change per commit.

---

# Pull Requests

Before opening a PR:

```bash
uv run ruff check <file_path>
uv run ruff format --check <file_path>
```

The PR description should briefly explain:

### What changed?

Describe the implementation.

### Why?

Explain the problem or requirement being addressed.

### How was it tested?

For distributed behavior, include useful verification details.

For example:

```text
Started two worker processes and verified both workers
appeared independently in the node registry.

Killed one worker and verified its heartbeat expired
after the configured TTL.
```

---

# Keep PRs Focused

Avoid combining unrelated changes.

Prefer:

```text
PR: Add worker heartbeat
```

over:

```text
PR: Add heartbeat + refactor broker + rewrite tests + change API
```

If a refactor is required for a feature, keep it limited to what the feature needs.

---

# Documentation

Update documentation when behavior visible to developers or users changes.

Examples:

* New environment variables
* New API endpoints
* New task types
* New Redis structures
* New development commands
* New architectural behavior

Keep `README.md` focused on using and understanding the project.

Keep implementation-specific discussion in code comments, issues, or PR descriptions.

---

# Current Development Direction

The project is being developed incrementally around distributed task-queue concepts.

The general progression is:

```text
Task persistence
        ↓
Priority queues
        ↓
Atomic task claiming
        ↓
Worker execution
        ↓
Leases / visibility timeout
        ↓
Retries and backoff
        ↓
Dead-letter queue
        ↓
Delayed scheduling
        ↓
Metrics
        ↓
Task events / worker state
        ↓
Cluster membership / heartbeats
        ↓
Stale-node cleanup
```

When implementing a new feature, preserve the existing abstractions instead of bypassing them.

---

# Questions and Issues

If you find a bug or have an architectural question, open a GitHub issue with:

* A short description
* Expected behavior
* Actual behavior
* Steps to reproduce
* Relevant logs/errors
* Redis state or task state when applicable

For feature proposals, explain the problem first and then the proposed solution.

---

# Final Checklist

Before submitting a contribution:

* [ ] Code follows the existing project structure.
* [ ] New behavior has appropriate tests.
* [ ] `uv run ruff check <file_path>` passes.
* [ ] `uv run ruff format <file_path> --check .` passes.
* [ ] No unnecessary changes are included.
* [ ] Redis operations preserve required atomicity.
* [ ] Failure and shutdown behavior has been considered.
* [ ] Commit messages clearly describe the changes.
