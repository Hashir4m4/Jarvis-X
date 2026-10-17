"""
Secure Remote JARVIS Access Controller.
Prompt 82 — Secure Remote Access.
"""
import logging
import secrets
import time
from typing import Dict, Any, List, Optional
from collections import defaultdict
import uuid

from backend.remote.models import (
    RemoteAccessRole, RemoteSessionState, RemoteAccessConfig, RemoteAccessSession, RemoteAuthResult
)

logger = logging.getLogger("JARVIS.RemoteAccess")


class SecureRemoteAccessGateway:
    """
    Guarded Remote Entry Gateway.
    Strict Security Rules:
    - Disabled by default. Explicit user activation required.
    - Anti brute-force lockouts per client IP.
    - Token replay and session expiry protections.
    - Zero remote shell or arbitrary code execution endpoints.
    - Instant revocation and emergency kill switch.
    """

    def __init__(self, config: Optional[RemoteAccessConfig] = None):
        self.config = config or RemoteAccessConfig()
        self._sessions: Dict[str, RemoteAccessSession] = {}  # token -> session
        self._failed_attempts: Dict[str, List[float]] = defaultdict(list)  # ip -> list of timestamps
        self._pre_shared_keys: Dict[str, str] = {}  # client_id -> psk

    def register_client_credential(self, client_id: str, psk: str):
        self._pre_shared_keys[client_id] = psk

    def enable_remote_access(self):
        self.config.enabled = True
        logger.info("Remote access enabled by user.")

    def disable_remote_access(self):
        self.config.enabled = False
        # Terminate all active sessions immediately
        for sess in self._sessions.values():
            sess.state = RemoteSessionState.TERMINATED
        logger.warning("Remote access disabled immediately; all active sessions terminated.")

    def authenticate_client(self, client_id: str, secret_key: str, client_ip: str, role: RemoteAccessRole = RemoteAccessRole.OPERATOR) -> RemoteAuthResult:
        if not self.config.enabled:
            return RemoteAuthResult(success=False, error_message="Remote access is currently disabled.")

        now = time.time()
        # Clean expired failed attempt window
        attempts = [t for t in self._failed_attempts[client_ip] if now - t < self.config.lockout_duration_seconds]
        self._failed_attempts[client_ip] = attempts

        if len(attempts) >= self.config.max_failed_attempts:
            logger.warning(f"Client IP {client_ip} is currently locked out due to excessive failed attempts.")
            return RemoteAuthResult(success=False, is_locked_out=True, error_message="Client IP temporarily locked out.")

        expected_psk = self._pre_shared_keys.get(client_id)
        if not expected_psk or not secrets.compare_digest(expected_psk, secret_key):
            self._failed_attempts[client_ip].append(now)
            logger.warning(f"Failed remote authentication attempt from {client_ip} for client {client_id}")
            return RemoteAuthResult(success=False, error_message="Invalid credentials.")

        # Success - create session
        token = secrets.token_urlsafe(32)
        sess = RemoteAccessSession(
            session_id=f"rem_{uuid.uuid4().hex[:10]}",
            client_id=client_id,
            client_ip=client_ip,
            role=role,
            token=token,
            expires_at=now + self.config.session_timeout_seconds
        )
        self._sessions[token] = sess
        # Clear failures for this IP upon success
        self._failed_attempts.pop(client_ip, None)
        return RemoteAuthResult(success=True, session=sess)

    def validate_request(self, token: str, required_role: Optional[RemoteAccessRole] = None) -> Optional[RemoteAccessSession]:
        if not self.config.enabled:
            return None

        sess = self._sessions.get(token)
        if not sess or not sess.is_valid():
            return None

        if required_role == RemoteAccessRole.ADMIN and sess.role != RemoteAccessRole.ADMIN:
            logger.warning(f"Access denied: session {sess.session_id} does not possess ADMIN role.")
            return None

        return sess

    def revoke_session(self, token: str) -> bool:
        sess = self._sessions.get(token)
        if not sess:
            return False
        sess.state = RemoteSessionState.REVOKED
        return True
