"""
JARVIS Extension Marketplace & Registry Service.
Prompt 85 — Extension Marketplace Architecture.
"""
import hashlib
import json
import logging
import time
from typing import Dict, Any, List, Optional
import uuid

from backend.marketplace.models import (
    ExtensionStatus, ExtensionPermissionScope, ExtensionManifest, InstalledExtensionRecord
)

logger = logging.getLogger("JARVIS.Marketplace")


class ExtensionRegistryService:
    """
    Local Extension Registry, Sandboxed Manifest Validator & Lifecycle Manager.
    Guarantees:
    - Zero silent installations. User approval required for requested permissions.
    - Package integrity checks via cryptographic checksums.
    - Rejection of wildcard '*' or undeclared dangerous permissions.
    - Instant quarantining and uninstallation lifecycle.
    """

    def __init__(self):
        # extension_id -> InstalledExtensionRecord
        self._installed: Dict[str, InstalledExtensionRecord] = {}

    def install_extension(
        self,
        manifest_data: Dict[str, Any],
        package_bytes: Optional[bytes] = None,
        expected_checksum: Optional[str] = None,
        approved_permissions: Optional[List[ExtensionPermissionScope]] = None
    ) -> tuple[bool, Optional[InstalledExtensionRecord], str]:
        try:
            scopes = [ExtensionPermissionScope(p) for p in manifest_data.get("required_permissions", [])]
            manifest = ExtensionManifest(
                extension_id=manifest_data["extension_id"],
                name=manifest_data["name"],
                version=manifest_data["version"],
                author=manifest_data.get("author", "Unknown"),
                description=manifest_data.get("description", ""),
                required_permissions=scopes,
                min_jarvis_version=manifest_data.get("min_jarvis_version", "1.0.0"),
                dependencies=manifest_data.get("dependencies", [])
            )
        except Exception as e:
            return False, None, f"Manifest parsing failed: {str(e)}"

        valid, err = manifest.validate()
        if not valid:
            return False, None, f"Invalid manifest: {err}"

        # Verify integrity if package bytes provided
        if package_bytes:
            computed_sum = hashlib.sha256(package_bytes).hexdigest()
            manifest.checksum = computed_sum
            if expected_checksum and computed_sum != expected_checksum:
                logger.error(f"Package integrity failure for {manifest.extension_id}!")
                return False, None, "Integrity verification failed: checksum mismatch."

        # Verify permission approval
        approved = approved_permissions or []
        for req in manifest.required_permissions:
            if req not in approved:
                return False, None, f"Installation blocked: Permission '{req.value}' not approved by user."

        record = InstalledExtensionRecord(
            manifest=manifest,
            status=ExtensionStatus.ENABLED,
            approved_permissions=approved,
            audit_events=[f"Installed and enabled at {time.time()}"]
        )
        self._installed[manifest.extension_id] = record
        logger.info(f"Successfully installed and enabled extension '{manifest.name}' ({manifest.extension_id})")
        return True, record, "Extension installed successfully."

    def disable_extension(self, extension_id: str) -> bool:
        record = self._installed.get(extension_id)
        if not record:
            return False
        record.status = ExtensionStatus.DISABLED
        record.audit_events.append(f"Disabled at {time.time()}")
        logger.info(f"Disabled extension {extension_id}")
        return True

    def enable_extension(self, extension_id: str) -> bool:
        record = self._installed.get(extension_id)
        if not record:
            return False
        record.status = ExtensionStatus.ENABLED
        record.audit_events.append(f"Enabled at {time.time()}")
        return True

    def quarantine_extension(self, extension_id: str, reason: str) -> bool:
        record = self._installed.get(extension_id)
        if not record:
            return False
        record.status = ExtensionStatus.QUARANTINED
        record.audit_events.append(f"Quarantined at {time.time()}: {reason}")
        logger.warning(f"Quarantined extension {extension_id}: {reason}")
        return True

    def uninstall_extension(self, extension_id: str) -> bool:
        if extension_id in self._installed:
            del self._installed[extension_id]
            logger.info(f"Uninstalled extension {extension_id}")
            return True
        return False

    def list_extensions(self) -> List[Dict[str, Any]]:
        return [
            {
                "manifest": rec.manifest.to_dict(),
                "status": rec.status.value,
                "installed_at": rec.installed_at,
                "approved_permissions": [p.value for p in rec.approved_permissions]
            }
            for rec in self._installed.values()
        ]

    def verify_action_permission(self, extension_id: str, scope: ExtensionPermissionScope) -> bool:
        record = self._installed.get(extension_id)
        if not record or record.status != ExtensionStatus.ENABLED:
            return False
        return scope in record.approved_permissions
