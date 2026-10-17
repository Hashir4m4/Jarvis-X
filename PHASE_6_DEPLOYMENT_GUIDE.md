# PHASE 6 DEPLOYMENT GUIDE

## 1. Prerequisites
- Python 3.11+
- Platform: Windows 10/11 (tested on Windows 11), Linux, macOS
- Optional network adapters for Home Assistant, MQTT, or OAuth 2.0 provider integrations

## 2. Environment Variables & Secrets
- `JARVIS_ENV`: `development` | `staging` | `production` (default: `development`)
- `JARVIS_REMOTE_ENABLED`: `false` (default: disabled)
- `JARVIS_CLOUD_ENABLED`: `false` (default: disabled)
- `JARVIS_SECRET_KEY`: Machine-specific cryptographic key for token signing

## 3. Launching Connected Subsystems
All Phase 6 subsystems initialize deterministically through `AppContainer` upon `JarvisCore` boot.
```python
from backend.core.core import JarvisCore

core = JarvisCore()
await core.start()
```

## 4. Enabling Optional Remote Access & Cloud Sync
```python
# Remote Access
core.remote_gateway.enable_remote_access()

# Personal Cloud Sync
core.personal_cloud.enable_cloud_sync()
```
