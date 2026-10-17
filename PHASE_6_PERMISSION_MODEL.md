# PHASE 6 PERMISSION MODEL

## Granular Capability Scopes

### 1. Mobile Companion Permissions (`backend/mobile/models.py`)
- `read:status`: Query JARVIS runtime status and subsystem health.
- `read:notifications`: View application notifications and system alerts.
- `read:goals`: Inspect strategic plans and active goals.
- `exec:commands`: Submit validated, non-destructive natural language queries.

### 2. Remote Access Roles (`backend/remote/models.py`)
- `VIEWER`: Read-only queries to telemetry and notifications.
- `OPERATOR`: Interactive query processing, task inspection, and safe commands.
- `ADMIN`: Configuration adjustments, connector updates, and emergency recovery.

### 3. Extension Permissions (`backend/marketplace/models.py`)
- `read:notifications`: Query notification feeds.
- `post:notifications`: Publish application notifications.
- `read:status`: Inspect core runtime status.
- `read:workspace`: Read workspace context within authorized roots.
- `exec:commands`: Execute registered non-privileged assistant skills.
- `hardware:control`: Issue safe hardware adjustments.
- `network:access`: Inbound/outbound external network calls.
- **Strict Rule**: Wildcard permissions (`*`) are prohibited and rejected by manifest validation.
