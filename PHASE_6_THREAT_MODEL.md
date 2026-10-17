# PHASE 6 THREAT MODEL & SECURITY REVIEW

| Threat Category | Potential Impact | Mitigation Strategy | Verification Evidence |
|---|---|---|---|
| **Credential & Key Theft** | Exposure of external connector tokens | API connectors redact secrets upon serialization (`to_safe_dict()`). Immediate revocation clears credentials from memory. | `tests/test_api_connectors.py` |
| **High-Impact Device Tampering** | Unauthorized door unlocking or disarming | Enforces `SmartDeviceSafetyTier.HIGH_IMPACT` with confirmation tokens. Stale/offline devices rejected. | `tests/test_smart_home.py` |
| **Telemetry Denial of Service** | Memory exhaustion via telemetry spam | Bounded ring buffers (`deque(maxlen=N)`), timestamp-based deduplication, and rate limiting. | `tests/test_iot_intelligence.py` |
| **Hardware Driver / UEFI Tampering** | System instability or hardware damage | Strict hardware privilege tiers. Privileged power/reset operations require human approval token. | `tests/test_hardware_control.py` |
| **Compromised Mobile Device** | Unauthorized remote system manipulation | Per-device identity registration with instant device revocation invalidating all active sessions. | `tests/test_mobile_companion.py` |
| **Cross-Device Sync Conflicts** | State corruption or resurrected deletions | Versioned records, deterministic conflict resolution policies, and soft-delete tombstones. | `tests/test_cross_device_sync.py` |
| **Remote Brute-Force Attacks** | Credential guessing on exposed endpoints | Disabled-by-default gateway, exponential lockout duration after 5 failed attempts, timing attack safe comparisons (`secrets.compare_digest`). | `tests/test_remote_access.py` |
| **Cloud Tenant Data Leakage** | Cross-user data compromise | Strict user-id partitioning, encryption, and SHA-256 integrity checksum verification on restore. | `tests/test_personal_cloud.py` |
| **Malicious Extension Supply-Chain** | Arbitrary code execution or data exfiltration | Sandboxed manifest validation, user consent enforcement, wildcard prohibition, and SHA-256 package verification. | `tests/test_marketplace.py` |
