# Tachikoma connection contract v1

This project was missing from `D:\AI\tachikoma\docs\production-connection-project-prompts-v1.md`.
The user explicitly approved a project-local contract on 2026-08-12. This file does not
change the Tachikoma control-plane repository or any other project's port.

- Project: `xiaohongshu-mcp`
- Default local endpoint: `http://127.0.0.1:18060` (loopback only)
- Port override: `XHS_MCP_PORT`
- Stable identity: `GET /healthz`
- Contract inspection: `GET /tachikoma/v1/contract`
- Unique service identity: `xiaohongshu-mcp`
- Contract version: `v1`
- Reproducible start: `powershell -ExecutionPolicy Bypass -File scripts\start_tachikoma_connection.ps1 -EnableProductionRead`
- Isolated test port: add `-Port 18061` (valid range 1–65535)

The start script builds a fresh loopback-only executable from the checked-in source before
launching it. Binaries, logs, QR images, cookies, and local connection state are excluded from
version control.

Read adapters describe existing search, detail, and profile endpoints. They are production
collection operations and require a task-specific collection authorization at the orchestrator
boundary. On 2026-08-24, search plus one bounded detail read passed under a current user-approved
read-only task. The run did not paginate all comments, expose write tools, persist platform
content, or perform a comment/follow/publish/profile action. This receipt does not authorize
future reads and is not an SLA claim.

Existing external-side-effect endpoints are guarded without changing their business handlers.
They fail closed unless all of the following are present:

1. `XHS_MCP_PRODUCTION_EXECUTION_ENABLED=true`
2. `X-Tachikoma-Expected-Service: xiaohongshu-mcp`
3. non-empty `X-Tachikoma-Task-ID`
4. non-empty `X-Tachikoma-Approval-ID`
5. non-empty `Idempotency-Key`
6. optional `X-Tachikoma-Timeout-Ms` is a positive integer not greater than 30000

The connection change does not grant approval. The environment switch and request headers are
necessary but do not replace the user's fresh task-specific approval.

Idempotency keys are process-local and retained even when a downstream handler returns an error.
This intentionally prevents automatic replay when an external side effect may have happened but
its result is unknown. A service restart clears the in-memory registry, so callers must still use
their durable task ledger before any approved retry.
