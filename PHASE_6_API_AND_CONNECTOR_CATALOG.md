# PHASE 6 API AND CONNECTOR CATALOG

## 1. Standard Connectors (`backend/connectors/`)
- **Connector Interface**: Declares `connector_id`, `name`, `version`, `provider`, `auth_type`, `credentials`, `permission_scopes`, `rate_limit`, `timeout_seconds`, and `circuit_breaker`.
- **Supported Auth Schemes**: `API_KEY`, `BEARER_TOKEN`, `OAUTH2`, `BASIC`, `NONE`.
- **Circuit Breaker**: Automatically opens upon repeated failures (threshold: 5 failures) and transitions to `HALF_OPEN` after recovery timeout.
- **Credential Protection**: Redacts secrets via `to_safe_dict()` serialization.

## 2. Smart Home Adapters (`backend/smarthome/`)
- **Device Classifications**: `LIGHT`, `SWITCH`, `THERMOSTAT`, `SENSOR`, `LOCK`, `MEDIA_PLAYER`, `SECURITY_GATEWAY`.
- **Safety Tiers**:
  - `STANDARD`: Safe operations (e.g., lights on/off, query status).
  - `CONTROLLED`: Regulated adjustments (e.g., thermostat target).
  - `HIGH_IMPACT`: Unlocking doors, access gates, security disarm. Strict human confirmation token required.

## 3. IoT Device Protocols (`backend/iot/`)
- **Telemetry Ingestion**: Ingests normalized data points (`device_id`, `metric_name`, `value`, `unit`, `timestamp`).
- **Buffers**: Fixed-capacity ring buffers preventing unbounded memory consumption.
- **Anomaly Detection**: Evaluates incoming telemetry against configured threshold ranges, flags anomalies, and logs auditable events.

## 4. Hardware Adapters (`backend/hardware/`)
- **Categories**: `AUDIO`, `DISPLAY`, `POWER`, `GPU`, `PERIPHERAL`, `SYSTEM_RESOURCE`.
- **Privilege Enforcement**: Privileged hardware commands (power management, device resets) require approval tokens.
