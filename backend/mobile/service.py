"""
Mobile Companion Backend Management Service.
Prompt 80 — Mobile Companion System.
"""
import logging
import secrets
import time
from typing import Dict, Any, List, Optional
import uuid

from backend.mobile.models import (
    MobileDevicePlatform, MobileSessionStatus, MobileDeviceRegistration, MobileSession
)

logger = logging.getLogger("JARVIS.MobileCompanion")


class MobileCompanionService:
    """
    Manages Mobile Companion pairing, authentication, session tokens, and access scopes.
    Guarantees:
    - Lost/compromised mobile devices can be revoked independently.
    - Revoking a device instantly invalidates all associated sessions.
    - Server-side authorization checks required for all sensitive remote actions.
    - Zero plain backend secrets exposed to mobile tokens.
    """

    def __init__(self, token_ttl_seconds: int = 86400):
        self.token_ttl_seconds = token_ttl_seconds
        self._devices: Dict[str, MobileDeviceRegistration] = {}
        self._sessions: Dict[str, MobileSession] = {}  # token -> session

    def register_device(
        self,
        user_id: str,
        device_name: str,
        platform: MobileDevicePlatform = MobileDevicePlatform.PWA,
        push_token: Optional[str] = None
    ) -> MobileDeviceRegistration:
        dev_id = f"mob_{uuid.uuid4().hex[:12]}"
        device = MobileDeviceRegistration(
            device_id=dev_id,
            user_id=user_id,
            device_name=device_name,
            platform=platform,
            push_token=push_token
        )
        self._devices[dev_id] = device
        logger.info(f"Registered mobile device {dev_id} ({device_name}) for user {user_id}")
        return device

    def create_session(
        self,
        device_id: str,
        user_id: str,
        scopes: Optional[List[str]] = None
    ) -> Optional[MobileSession]:
        device = self._devices.get(device_id)
        if not device or device.revoked:
            logger.warning(f"Rejected session creation for revoked/unknown device {device_id}")
            return None

        device.last_active_at = time.time()
        token = secrets.token_urlsafe(32)
        session_id = f"sess_{uuid.uuid4().hex[:10]}"
        granted_scopes = scopes or ["read:status", "read:notifications", "read:goals", "exec:commands"]

        session = MobileSession(
            session_id=session_id,
            device_id=device_id,
            user_id=user_id,
            token=token,
            scopes=granted_scopes,
            expires_at=time.time() + self.token_ttl_seconds
        )
        self._sessions[token] = session
        return session

    def authenticate_token(self, token: str, required_scope: Optional[str] = None) -> Optional[MobileSession]:
        session = self._sessions.get(token)
        if not session or not session.is_valid():
            return None

        # Check if underlying device is revoked
        device = self._devices.get(session.device_id)
        if not device or device.revoked:
            session.status = MobileSessionStatus.REVOKED
            return None

        if required_scope and required_scope not in session.scopes:
            logger.warning(f"Session {session.session_id} missing required scope: {required_scope}")
            return None

        device.last_active_at = time.time()
        return session

    def revoke_device(self, device_id: str) -> bool:
        device = self._devices.get(device_id)
        if not device:
            return False

        device.revoked = True
        # Invalidate all active sessions for this device
        for session in self._sessions.values():
            if session.device_id == device_id:
                session.status = MobileSessionStatus.REVOKED

        logger.info(f"Revoked device {device_id} and all related sessions.")
        return True

    def revoke_session(self, token: str) -> bool:
        session = self._sessions.get(token)
        if not session:
            return False
        session.status = MobileSessionStatus.REVOKED
        return True

    def list_user_devices(self, user_id: str) -> List[Dict[str, Any]]:
        return [dev.to_safe_dict() for dev in self._devices.values() if dev.user_id == user_id]
