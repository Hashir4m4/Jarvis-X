import enum
import re
import logging
from typing import List, Dict, Any, Union

logger = logging.getLogger("JARVIS.PrivacyBoundary")


class ContextPrivacyLevel(enum.Enum):
    LOCAL_CONTEXT = "LOCAL_CONTEXT"
    CLOUD_ALLOWED_CONTEXT = "CLOUD_ALLOWED_CONTEXT"
    SENSITIVE_LOCAL_CONTEXT = "SENSITIVE_LOCAL_CONTEXT"


# Regex patterns targeting secrets, tokens, passwords, and private keys
SECRET_PATTERNS = [
    # OpenAI, Anthropic, Gemini, Groq API keys
    r"(sk-[a-zA-Z0-9_\-]{15,})",
    r"(sk-ant-[a-zA-Z0-9_\-]{10,})",
    r"(ant-api[a-zA-Z0-9_\-]{10,})",
    r"(AIzaSy[a-zA-Z0-9_\-]{20,})",
    r"(gsk_[a-zA-Z0-9_\-]{15,})",
    # GitHub, Slack, AWS tokens
    r"(ghp_[a-zA-Z0-9]{36})",
    r"(github_pat_[a-zA-Z0-9_]{30,})",
    r"(xox[baprs]-[0-9a-zA-Z_\-]{10,})",
    r"(AKIA[0-9A-Z]{16})",
    # Bearer Tokens & Auth headers
    r"(Bearer\s+[a-zA-Z0-9_\-\.]{20,})",
    # Passwords & API Key assignments
    r"((?:password|secret|api_key|token|access_key|auth_token)\s*[:=]\s*['\"]?)([^'\"\s\n]{6,})(['\"]?)",
    # Private Key blocks
    r"(-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----)"
]


class PrivacyBoundary:
    """
    Guarantees privacy and context isolation between local storage and cloud AI endpoints.
    Sanitizes prompts, strips credentials, redacts secrets, and enforces context boundary rules.
    """

    def __init__(self, redactor_replacement: str = "[REDACTED_SECRET]"):
        self.redactor_replacement = redactor_replacement
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in SECRET_PATTERNS]

    def redact_secrets(self, text: str) -> str:
        """Sanitizes text by replacing any discovered API keys, tokens, or credentials."""
        if not text:
            return ""
        sanitized = text
        for pat in self._compiled_patterns:
            sanitized = pat.sub(self.redactor_replacement, sanitized)
        return sanitized

    def sanitize_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Processes a list of chat message dictionaries and returns a new list
        with all sensitive secrets redacted before cloud transmission.
        """
        cleaned_messages = []
        for msg in messages:
            content = msg.get("content", "")
            cleaned_content = self.redact_secrets(content)
            cleaned_messages.append({
                "role": msg.get("role", "user"),
                "content": cleaned_content
            })
        return cleaned_messages

    def classify_context(self, text: str, source: str = "") -> ContextPrivacyLevel:
        """
        Categorizes context data into LOCAL_CONTEXT, CLOUD_ALLOWED_CONTEXT, or SENSITIVE_LOCAL_CONTEXT.
        """
        # Explicit sensitive files / sources
        lower_source = source.lower()
        if any(sens in lower_source for sens in (".env", "config.json", "vault/raw/tokens", "secrets")):
            return ContextPrivacyLevel.SENSITIVE_LOCAL_CONTEXT

        # Check for presence of unredacted credentials
        for pat in self._compiled_patterns:
            if pat.search(text):
                return ContextPrivacyLevel.SENSITIVE_LOCAL_CONTEXT

        return ContextPrivacyLevel.CLOUD_ALLOWED_CONTEXT

    def filter_memory_for_cloud(self, memory_snippets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filters out entire vault dumps or sensitive memory items,
        retaining only sanitized dialogue context.
        """
        permitted_snippets = []
        for snippet in memory_snippets:
            content = snippet.get("content", "")
            source = snippet.get("source", "")
            level = self.classify_context(content, source)

            if level != ContextPrivacyLevel.SENSITIVE_LOCAL_CONTEXT:
                permitted_snippets.append({
                    "role": snippet.get("role", "user"),
                    "content": self.redact_secrets(content)
                })
        return permitted_snippets
