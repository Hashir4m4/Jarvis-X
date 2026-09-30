"""
Hybrid Intelligent Model Router.

Deterministically selects the smallest and most appropriate AI intelligence
for each request based on task type, complexity, privacy, connectivity,
provider availability, latency requirements, user preferences, and cost.

This component sits between the JARVIS Intelligence Orchestrator's task
classification step and execution step. It does NOT invoke an LLM to decide
which model to use — all routing is rule-based and lightweight.
"""

import enum
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

from backend.core.models import TaskCategory
from backend.llm.local_models import LocalModelConfig
from backend.llm.cloud_models import CloudModelConfig
from backend.llm.privacy_boundary import PrivacyBoundary, ContextPrivacyLevel
from backend.llm.registry import ModelRegistry, ModelMetadata
from backend.llm.resource_manager import ResourceManager

logger = logging.getLogger("JARVIS.ModelRouter")


# ── Enums ──────────────────────────────────────────────────────────────────────


class PrivacyPolicy(str, enum.Enum):
    """Privacy routing policy controlling where data may be sent."""
    LOCAL_ONLY = "LOCAL_ONLY"
    PREFER_LOCAL = "PREFER_LOCAL"
    CLOUD_ALLOWED = "CLOUD_ALLOWED"


class UserRoutingPreference(str, enum.Enum):
    """User-level routing override."""
    AUTO = "AUTO"
    LOCAL = "LOCAL"
    CLOUD = "CLOUD"
    HYBRID = "HYBRID"


class RoutingStatus(str, enum.Enum):
    """Status of the model routing decision."""
    AVAILABLE = "AVAILABLE"
    PROCESSING = "PROCESSING"
    FALLBACK = "FALLBACK"
    NO_CAPABILITY = "NO_CAPABILITY"


class RequestComplexity(str, enum.Enum):
    """Estimated complexity of the request."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ModelRole(str, enum.Enum):
    """Functional role a model must fulfill for a given task."""
    NONE = "none"
    FAST = "fast"
    GENERAL = "general"
    REASONING = "reasoning"
    CODING = "coding"
    VISION = "vision"


# ── Data Classes ───────────────────────────────────────────────────────────────


@dataclass
class ModelSelectionRequest:
    """Structured input for the Model Router's select() method."""
    task_category: TaskCategory = TaskCategory.UNKNOWN
    user_input: str = ""
    complexity: RequestComplexity = RequestComplexity.MEDIUM
    privacy_level: PrivacyPolicy = PrivacyPolicy.PREFER_LOCAL
    internet_available: bool = False
    local_llm_available: bool = False
    cloud_available: bool = False
    cloud_providers: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    required_capabilities: List[str] = field(default_factory=list)
    latency_preference: str = "normal"  # "low", "normal", "high_quality"
    user_preference: UserRoutingPreference = UserRoutingPreference.AUTO
    source: str = "text"
    skill_name: Optional[str] = None


@dataclass
class ModelSelectionResult:
    """Structured output from the Model Router."""
    provider: str = "none"          # "none", "local", "openai", "anthropic", "gemini", "groq"
    model: Optional[str] = None     # e.g. "qwen2.5-coder:7b", "gpt-4o-mini"
    reason: str = ""                # Concise routing explanation for logs
    confidence: float = 1.0         # 0.0 – 1.0
    fallbacks: List[Dict[str, str]] = field(default_factory=list)
    routing_status: RoutingStatus = RoutingStatus.AVAILABLE
    required_capabilities: List[str] = field(default_factory=list)
    model_role: str = "general"     # The functional role that was selected


# ── Task → Role Mapping ───────────────────────────────────────────────────────

TASK_ROLE_MAP: Dict[TaskCategory, ModelRole] = {
    TaskCategory.COMMAND: ModelRole.NONE,
    TaskCategory.COMPUTER_ACTION: ModelRole.NONE,
    TaskCategory.SCHEDULED_TASK: ModelRole.FAST,
    TaskCategory.CONVERSATION: ModelRole.GENERAL,
    TaskCategory.QUESTION: ModelRole.GENERAL,
    TaskCategory.MEMORY_REQUEST: ModelRole.FAST,
    TaskCategory.CODING_TASK: ModelRole.CODING,
    TaskCategory.PLANNING_TASK: ModelRole.REASONING,
    TaskCategory.RESEARCH_TASK: ModelRole.REASONING,
    TaskCategory.VISION_TASK: ModelRole.VISION,
    TaskCategory.MULTI_STEP_TASK: ModelRole.REASONING,
    TaskCategory.UNKNOWN: ModelRole.GENERAL,
}

# Skills that can execute without any LLM involvement
NO_LLM_SKILLS = frozenset({
    "system", "metrics", "trends", "inbox", "vault",
})


# ── Model Router ───────────────────────────────────────────────────────────────


class ModelRouter:
    """
    Hybrid Intelligent Model Router.

    Deterministically selects the optimal AI provider and model for each request.
    All decisions are rule-based — no LLM is invoked for routing.

    Integrates with:
    - LocalModelConfig  (local model role mappings)
    - CloudModelConfig  (cloud model role mappings)
    - PrivacyBoundary   (context sensitivity detection)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.local_models = LocalModelConfig.from_config(self.config)
        self.cloud_models = CloudModelConfig.from_config(self.config)
        self.privacy_boundary = PrivacyBoundary()
        self.registry = ModelRegistry()
        self.resource_manager = ResourceManager()

        # Load default user preferences from config/env
        pref_str = (
            self.config.get("model_routing_preference")
            or os.getenv("MODEL_ROUTING_PREFERENCE", "AUTO")
        ).upper()
        try:
            self.default_user_preference = UserRoutingPreference(pref_str)
        except ValueError:
            self.default_user_preference = UserRoutingPreference.AUTO

        policy_str = (
            self.config.get("model_privacy_policy")
            or os.getenv("MODEL_PRIVACY_POLICY", "PREFER_LOCAL")
        ).upper()
        try:
            self.default_privacy_policy = PrivacyPolicy(policy_str)
        except ValueError:
            self.default_privacy_policy = PrivacyPolicy.PREFER_LOCAL

        logger.info(
            f"ModelRouter initialized: preference={self.default_user_preference.value}, "
            f"privacy={self.default_privacy_policy.value}"
        )

    # ── Public API ─────────────────────────────────────────────────────────

    def select(self, request: ModelSelectionRequest) -> ModelSelectionResult:
        """
        Core routing method. Returns a ModelSelectionResult describing which
        provider and model should handle this request.
        """
        # Apply defaults if caller didn't override
        if request.user_preference == UserRoutingPreference.AUTO:
            request.user_preference = self.default_user_preference
        if request.privacy_level == PrivacyPolicy.PREFER_LOCAL:
            request.privacy_level = self.default_privacy_policy

        # 1. Determine required model role from task category
        role = self._determine_role(request)

        # 2. NO_LLM path: direct system commands and tool-only skills
        if role == ModelRole.NONE:
            return ModelSelectionResult(
                provider="none",
                model=None,
                reason=f"Task '{request.task_category.value}' handled by direct tool/skill execution — no LLM required.",
                confidence=1.0,
                routing_status=RoutingStatus.AVAILABLE,
                model_role=role.value,
            )

        # 3. Detect privacy constraints from content
        content_privacy = self._detect_content_privacy(request)
        effective_privacy = self._resolve_effective_privacy(request.privacy_level, content_privacy)

        # 4. Build candidate list
        candidates = self._build_candidates(request, role, effective_privacy)

        # 5. Select best candidate
        if not candidates:
            return self._no_capability_result(request, role, effective_privacy)

        primary = candidates[0]
        fallbacks = [{"provider": c["provider"], "model": c["model"]} for c in candidates[1:]]

        return ModelSelectionResult(
            provider=primary["provider"],
            model=primary["model"],
            reason=primary["reason"],
            confidence=primary["confidence"],
            fallbacks=fallbacks,
            routing_status=RoutingStatus.AVAILABLE if primary["provider"] != "none" else RoutingStatus.NO_CAPABILITY,
            required_capabilities=request.required_capabilities,
            model_role=role.value,
        )

    def select_with_fallback(self, request: ModelSelectionRequest) -> ModelSelectionResult:
        """
        Selects a model and, if the primary is unavailable, automatically
        returns the first available fallback.
        """
        result = self.select(request)
        if result.routing_status == RoutingStatus.NO_CAPABILITY and result.fallbacks:
            fb = result.fallbacks[0]
            return ModelSelectionResult(
                provider=fb["provider"],
                model=fb["model"],
                reason=f"Primary unavailable. Falling back to {fb['provider']}:{fb['model']}.",
                confidence=0.7,
                fallbacks=result.fallbacks[1:],
                routing_status=RoutingStatus.FALLBACK,
                required_capabilities=result.required_capabilities,
                model_role=result.model_role,
            )
        return result

    # ── HUD Telemetry ──────────────────────────────────────────────────────

    def to_hud_payload(self, result: ModelSelectionResult) -> Dict[str, Any]:
        """
        Produces safe, non-sensitive routing telemetry for HUD display.
        """
        mode = "LOCAL"
        if result.provider == "none":
            mode = "DIRECT"
        elif result.provider == "local":
            mode = "LOCAL"
        elif result.provider in ("openai", "anthropic", "gemini", "groq"):
            mode = "CLOUD"

        return {
            "mode": mode,
            "active_provider": result.provider,
            "active_model": result.model or "none",
            "routing_status": result.routing_status.value,
            "model_role": result.model_role,
            "reason": result.reason,
        }

    # ── Internal Logic ─────────────────────────────────────────────────────

    def _determine_role(self, request: ModelSelectionRequest) -> ModelRole:
        """Maps task category + skill to the required model role."""
        # Direct tool/skill execution — no LLM needed
        if request.skill_name in NO_LLM_SKILLS:
            return ModelRole.NONE

        if request.task_category == TaskCategory.COMPUTER_ACTION:
            return ModelRole.NONE

        if request.task_category == TaskCategory.COMMAND and request.skill_name in NO_LLM_SKILLS:
            return ModelRole.NONE

        role = TASK_ROLE_MAP.get(request.task_category, ModelRole.GENERAL)

        # Upgrade role based on complexity
        if request.complexity == RequestComplexity.HIGH and role in (ModelRole.GENERAL, ModelRole.FAST):
            role = ModelRole.REASONING

        return role

    def _detect_content_privacy(self, request: ModelSelectionRequest) -> ContextPrivacyLevel:
        """Uses PrivacyBoundary to classify the request content."""
        return self.privacy_boundary.classify_context(request.user_input)

    def _resolve_effective_privacy(
        self,
        policy: PrivacyPolicy,
        content_privacy: ContextPrivacyLevel
    ) -> PrivacyPolicy:
        """
        Combines the configured privacy policy with content-level sensitivity detection.
        Sensitive content always forces LOCAL_ONLY regardless of policy.
        """
        if content_privacy == ContextPrivacyLevel.SENSITIVE_LOCAL_CONTEXT:
            return PrivacyPolicy.LOCAL_ONLY

        return policy

    def _build_candidates(
        self,
        request: ModelSelectionRequest,
        role: ModelRole,
        effective_privacy: PrivacyPolicy
    ) -> List[Dict[str, Any]]:
        """
        Builds an ordered list of provider/model candidates based on
        availability, privacy, user preference, and task role.
        """
        candidates = []
        cloud_blocked = (
            effective_privacy == PrivacyPolicy.LOCAL_ONLY
            or not request.internet_available
        )

        # ── Local candidates ──────────────────────────────────────────────
        if request.local_llm_available:
            local_model = self._get_local_model_for_role(role)
            local_reason = f"Local model selected for '{role.value}' role."

            if effective_privacy == PrivacyPolicy.LOCAL_ONLY:
                local_reason = f"Privacy policy LOCAL_ONLY: local model selected for '{role.value}' role."

            # Check capabilities from registry
            metadata = self.registry.get_model(local_model)
            if not metadata:
                # Mock metadata if not registered
                metadata = ModelMetadata(model_id=local_model, provider="local", local_or_online="local")
            
            # Capability filters
            if "vision" in request.required_capabilities and not metadata.capabilities.vision:
                local_reason = f"Local model {local_model} lacks required vision capabilities."
            elif not self.resource_manager.can_load_model(metadata):
                local_reason = f"Insufficient local resources to load model {local_model}."
            else:
                candidates.append({
                    "provider": "local",
                    "model": local_model,
                    "reason": local_reason,
                    "confidence": 0.9,
                    "score": self._score_candidate(
                        is_local=True,
                        role=role,
                        request=request,
                        effective_privacy=effective_privacy,
                    ),
                })

        # ── Cloud candidates ──────────────────────────────────────────────
        if not cloud_blocked and request.cloud_available:
            cloud_candidates = self._get_cloud_candidates(request, role, effective_privacy)
            candidates.extend(cloud_candidates)

        # ── Sort by score (descending) ────────────────────────────────────
        candidates.sort(key=lambda c: c["score"], reverse=True)

        # ── Apply user preference re-ordering ─────────────────────────────
        candidates = self._apply_user_preference(candidates, request.user_preference, cloud_blocked)

        return candidates

    def _get_local_model_for_role(self, role: ModelRole) -> str:
        """Maps a model role to the configured local model."""
        role_map = {
            ModelRole.FAST: self.local_models.fast_model,
            ModelRole.GENERAL: self.local_models.general_model,
            ModelRole.REASONING: self.local_models.reasoning_model,
            ModelRole.CODING: self.local_models.coding_model,
            ModelRole.VISION: self.local_models.vision_model,
        }
        return role_map.get(role, self.local_models.general_model)

    def _get_cloud_candidates(
        self,
        request: ModelSelectionRequest,
        role: ModelRole,
        effective_privacy: PrivacyPolicy
    ) -> List[Dict[str, Any]]:
        """Generates scored cloud provider candidates for the given role."""
        candidates = []
        cloud_model = self._get_cloud_model_for_role(role)

        for provider_name, status in request.cloud_providers.items():
            if not status.get("available", False):
                continue

            reason = f"Cloud provider '{provider_name}' selected for '{role.value}' role."
            if effective_privacy == PrivacyPolicy.CLOUD_ALLOWED:
                reason = f"Cloud allowed: '{provider_name}' selected for '{role.value}' role."

            # Check capabilities from registry
            metadata = self.registry.get_model(cloud_model)
            if not metadata:
                metadata = ModelMetadata(model_id=cloud_model, provider=provider_name, local_or_online="online")
                
            if "vision" in request.required_capabilities and not metadata.capabilities.vision:
                reason = f"Cloud model {cloud_model} lacks required vision capabilities."
                continue

            candidates.append({
                "provider": provider_name,
                "model": cloud_model,
                "reason": reason,
                "confidence": 0.85,
                "score": self._score_candidate(
                    is_local=False,
                    role=role,
                    request=request,
                    effective_privacy=effective_privacy,
                    provider_name=provider_name,
                ),
            })

        return candidates

    def _get_cloud_model_for_role(self, role: ModelRole) -> str:
        """Maps a model role to the configured cloud model."""
        role_map = {
            ModelRole.FAST: self.cloud_models.fast_model,
            ModelRole.GENERAL: self.cloud_models.general_model,
            ModelRole.REASONING: self.cloud_models.reasoning_model,
            ModelRole.CODING: self.cloud_models.coding_model,
            ModelRole.VISION: self.cloud_models.vision_model,
        }
        return role_map.get(role, self.cloud_models.general_model)

    def _score_candidate(
        self,
        is_local: bool,
        role: ModelRole,
        request: ModelSelectionRequest,
        effective_privacy: PrivacyPolicy,
        provider_name: str = "local",
    ) -> float:
        """
        Scores a candidate provider/model on a 0.0–1.0 scale.
        Higher = more preferred.
        """
        score = 0.5  # Base score

        # Privacy bonus: local candidates get a boost under PREFER_LOCAL
        if is_local:
            if effective_privacy in (PrivacyPolicy.LOCAL_ONLY, PrivacyPolicy.PREFER_LOCAL):
                score += 0.3
            else:
                score += 0.1
        else:
            if effective_privacy == PrivacyPolicy.CLOUD_ALLOWED:
                score += 0.2

        # Latency: local is faster for low-latency requests
        if request.latency_preference == "low":
            if is_local:
                score += 0.15
            else:
                score -= 0.1

        # Capability: cloud often has stronger reasoning/coding
        if role in (ModelRole.REASONING, ModelRole.CODING) and not is_local:
            score += 0.1

        # Research tasks benefit from cloud (online tools + better models)
        if request.task_category == TaskCategory.RESEARCH_TASK and not is_local:
            score += 0.1

        # Vision: check cloud vision models are typically stronger
        if role == ModelRole.VISION and not is_local:
            score += 0.05

        return min(max(score, 0.0), 1.0)

    def _apply_user_preference(
        self,
        candidates: List[Dict[str, Any]],
        preference: UserRoutingPreference,
        cloud_blocked: bool
    ) -> List[Dict[str, Any]]:
        """Re-orders candidates based on explicit user preference."""
        if not candidates or preference == UserRoutingPreference.AUTO:
            return candidates

        if preference == UserRoutingPreference.LOCAL:
            # Local candidates first
            local = [c for c in candidates if c["provider"] == "local"]
            cloud = [c for c in candidates if c["provider"] != "local"]
            return local + cloud

        if preference == UserRoutingPreference.CLOUD and not cloud_blocked:
            # Cloud candidates first
            cloud = [c for c in candidates if c["provider"] != "local"]
            local = [c for c in candidates if c["provider"] == "local"]
            return cloud + local

        if preference == UserRoutingPreference.HYBRID:
            # Keep score-based ordering (default behavior)
            return candidates

        return candidates

    def _no_capability_result(
        self,
        request: ModelSelectionRequest,
        role: ModelRole,
        effective_privacy: PrivacyPolicy
    ) -> ModelSelectionResult:
        """Returns a structured result when no capable provider is available."""
        if effective_privacy == PrivacyPolicy.LOCAL_ONLY and not request.local_llm_available:
            reason = (
                "Privacy policy requires LOCAL_ONLY processing but no local LLM is available. "
                "Cannot route to cloud providers."
            )
        elif not request.internet_available and not request.local_llm_available:
            reason = (
                "No AI capability available: local LLM is offline and internet is unavailable. "
                "System tools and direct skills remain functional."
            )
        elif not request.local_llm_available and not request.cloud_available:
            reason = (
                "No AI providers available: local LLM is offline and no cloud providers are configured/accessible."
            )
        else:
            reason = f"No capable provider found for role '{role.value}'."

        return ModelSelectionResult(
            provider="none",
            model=None,
            reason=reason,
            confidence=0.0,
            routing_status=RoutingStatus.NO_CAPABILITY,
            model_role=role.value,
        )


# ── Complexity Classification ──────────────────────────────────────────────────


def classify_complexity(user_input: str, task_category: TaskCategory) -> RequestComplexity:
    """
    Estimates request complexity from token count, keyword analysis, and task category.
    Lightweight heuristic — no LLM invocation.
    """
    lower = user_input.lower()
    word_count = len(user_input.split())

    # High complexity indicators
    high_keywords = (
        "compare", "tradeoff", "trade-off", "analyze", "evaluate",
        "architecture", "design", "refactor", "optimize", "implement",
        "debug", "migrate", "integrate", "complex", "multi-step",
        "pros and cons", "deep dive", "in depth", "comprehensive",
    )
    if any(kw in lower for kw in high_keywords):
        return RequestComplexity.HIGH

    # Task categories that are inherently complex
    if task_category in (TaskCategory.MULTI_STEP_TASK, TaskCategory.RESEARCH_TASK):
        return RequestComplexity.HIGH

    if task_category == TaskCategory.CODING_TASK:
        return RequestComplexity.HIGH if word_count > 15 else RequestComplexity.MEDIUM

    # Low complexity indicators
    if word_count <= 5:
        return RequestComplexity.LOW

    if task_category in (TaskCategory.COMMAND, TaskCategory.COMPUTER_ACTION):
        return RequestComplexity.LOW

    if task_category == TaskCategory.CONVERSATION and word_count <= 10:
        return RequestComplexity.LOW

    return RequestComplexity.MEDIUM


def detect_privacy_level(
    user_input: str,
    task_category: TaskCategory,
    default_policy: PrivacyPolicy = PrivacyPolicy.PREFER_LOCAL
) -> PrivacyPolicy:
    """
    Determines the effective privacy level for a request.
    Uses PrivacyBoundary for content-level secret detection.
    """
    boundary = PrivacyBoundary()
    content_level = boundary.classify_context(user_input)

    if content_level == ContextPrivacyLevel.SENSITIVE_LOCAL_CONTEXT:
        return PrivacyPolicy.LOCAL_ONLY

    # Memory requests often contain personal context
    if task_category == TaskCategory.MEMORY_REQUEST:
        if default_policy != PrivacyPolicy.CLOUD_ALLOWED:
            return PrivacyPolicy.LOCAL_ONLY

    return default_policy
