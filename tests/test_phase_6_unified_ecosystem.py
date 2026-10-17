"""
Integration Tests for Phase 6 — Connected Intelligence Ecosystem.
Prompts 76–85 Unified Lifecycle and Service Contracts.
"""
import pytest
from backend.core.core import JarvisCore
from backend.connectors.models import ConnectorConfig, AuthType
from backend.smarthome.models import SmartDevice, SmartDeviceType, SmartDeviceSafetyTier
from backend.iot.models import IoTTelemetryPoint, IoTDeviceRegistration
from backend.hardware.models import HardwareCategory, HardwarePrivilegeLevel
from backend.mobile.models import MobileDevicePlatform
from backend.sync.models import SyncCategory
from backend.remote.models import RemoteAccessRole
from backend.cloud.models import CloudSyncScope
from backend.marketplace.models import ExtensionPermissionScope
from backend.sdk.client import JarvisSDKClient, SDKClientConfig


@pytest.fixture
def core_instance():
    cfg = {
        "storage": {"vault_path": "vault"},
        "voice": {"mode": "MANUAL"}
    }
    core = JarvisCore(config=cfg, session_id="phase6_test_session")
    return core


@pytest.mark.asyncio
async def test_phase_6_connected_subsystems_initialization(core_instance):
    # Verify all 10 Phase 6 services are registered and initialized
    assert core_instance.connector_registry is not None
    assert core_instance.smarthome_service is not None
    assert core_instance.iot_service is not None
    assert core_instance.hardware_control is not None
    assert core_instance.mobile_companion is not None
    assert core_instance.sync_engine is not None
    assert core_instance.remote_gateway is not None
    assert core_instance.personal_cloud is not None
    assert core_instance.marketplace is not None


@pytest.mark.asyncio
async def test_phase_6_end_to_end_connected_flow(core_instance):
    # 1. API Connector
    conn_cfg = ConnectorConfig(
        connector_id="weather_api",
        name="Global Weather",
        version="1.0.0",
        provider="open_weather",
        auth_type=AuthType.API_KEY,
        credentials={"api_key": "sec_test_99"}
    )
    core_instance.connector_registry.register_connector(conn_cfg)
    assert core_instance.connector_registry.get_connector_status("weather_api") is not None

    # 2. Smart Home & High-Impact Gate
    dev = SmartDevice(
        device_id="door_front",
        name="Front Door",
        provider="homeassistant",
        device_type=SmartDeviceType.LOCK,
        safety_tier=SmartDeviceSafetyTier.HIGH_IMPACT
    )
    core_instance.smarthome_service.register_device(dev)
    # Block unconfirmed unlock
    res_gate = await core_instance.smarthome_service.execute_device_command("door_front", "unlock", {})
    assert res_gate.success is False
    assert res_gate.requires_confirmation is True

    # 3. IoT Anomaly Ingestion
    core_instance.iot_service.register_device(IoTDeviceRegistration(
        device_id="sensor_temp",
        device_name="Server Rack Thermostat",
        device_type="thermostat",
        thresholds={"temperature": (15.0, 35.0)}
    ))
    ok = core_instance.iot_service.ingest_telemetry(IoTTelemetryPoint(
        point_id="p1", device_id="sensor_temp", metric_name="temperature", value=42.0, unit="C"
    ))
    assert ok is True
    assert len(core_instance.iot_service.get_anomalies("sensor_temp")) == 1

    # 4. Hardware Control Approval Gate
    res_hw = await core_instance.hardware_control.execute_hardware_action(
        "power_subsystem", "set_power_plan", {"plan": "MaximumPerformance"}
    )
    assert res_hw.requires_approval is True

    # 5. Mobile Companion Pairing & Session
    mob = core_instance.mobile_companion.register_device("user_root", "Pixel 9", MobileDevicePlatform.ANDROID)
    sess = core_instance.mobile_companion.create_session(mob.device_id, "user_root")
    assert sess is not None
    assert core_instance.mobile_companion.authenticate_token(sess.token) is not None

    # 6. Cross-Device Sync
    sync_res = core_instance.sync_engine.push_record(
        user_id="user_root",
        record_id="theme_setting",
        category=SyncCategory.USER_PREFERENCES,
        version=1,
        payload={"accent": "neon_blue"},
        source_device_id=mob.device_id
    )
    assert sync_res.success is True
    pulled = core_instance.sync_engine.pull_changes("user_root")
    assert len(pulled) == 1

    # 7. Secure Remote Access Gateway (Disabled by default)
    core_instance.remote_gateway.register_client_credential("remote_laptop", "psk_passcode")
    auth_denied = core_instance.remote_gateway.authenticate_client("remote_laptop", "psk_passcode", "1.2.3.4")
    assert auth_denied.success is False  # default disabled

    core_instance.remote_gateway.enable_remote_access()
    auth_ok = core_instance.remote_gateway.authenticate_client("remote_laptop", "psk_passcode", "1.2.3.4")
    assert auth_ok.success is True

    # 8. Personal Cloud Backup & Checksum Verification
    core_instance.personal_cloud.enable_cloud_sync()
    bak = core_instance.personal_cloud.create_encrypted_backup("user_root", CloudSyncScope.SETTINGS_AND_CONFIG, {"accent": "neon_blue"})
    assert bak is not None
    ok, data, _ = core_instance.personal_cloud.restore_backup("user_root", bak.backup_id)
    assert ok is True
    assert data["accent"] == "neon_blue"

    # 9. Marketplace Extension Registry
    manifest = {
        "extension_id": "ext_monitor",
        "name": "System Monitor",
        "version": "1.0.0",
        "required_permissions": ["read:status"]
    }
    installed, _, _ = core_instance.marketplace.install_extension(
        manifest, approved_permissions=[ExtensionPermissionScope.READ_STATUS]
    )
    assert installed is True

    # 10. Developer SDK
    sdk = JarvisSDKClient(SDKClientConfig(token="test_token"))
    sdk_res = sdk.get_system_status()
    assert sdk_res.is_success is True
