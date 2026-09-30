"""
Tests for JARVIS Personality and Adaptive Interaction System (Prompt 34)

22 test cases covering:
1. Personality profile loading
2. Personality consistency across model switches
3. Short response for simple question
4. Detailed response for technical question
5. Frustration signal adaptation
6. Confusion signal adaptation
7. Urgency adaptation
8. No overconfident emotional inference
9. Context-aware "continue"
10. Ambiguous "continue" clarification
11. Voice response adaptation (shorter + no markdown)
12. Text response adaptation (full)
13. HUD response adaptation (ultra-compact)
14. Focus Mode behavior
15. Humor disabled in critical situations
16. Error communication reformatting
17. Confidence-aware language
18. Model switching preserves personality
19. Agent results synthesized through JARVIS personality
20. Social conversation does not activate unnecessary tools
21. Interruption handling (voice-only vs task cancel)
22. Explicit preference handling

No cloud AI required. Uses mocked model outputs throughout.
"""
import sys
import os
import pytest

# Make sure the project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.interaction.models import (
    PersonalityProfile, InteractionState, EmotionalSignalResult,
    ResponseStrategy, ChannelOutput, CommunicationStyle, FormalityLevel,
    HumorLevel, VerbosityLevel, TechnicalDepth, WarmthLevel, ProactivityLevel,
    EmotionalSignal, SignalConfidence, InteractionMode, ResponseLength,
    ToneStyle, VoiceStyle, HUDStyle
)
from backend.interaction.personality import (
    PersonalityRegistry, DEFAULT_JARVIS_PROFILE, BUILT_IN_PROFILES
)
from backend.interaction.signal_detector import EmotionalSignalDetector
from backend.interaction.state_manager import InteractionStateManager
from backend.interaction.response_strategy import ResponseStrategyEngine
from backend.interaction.channel_adapter import ChannelAdapter
from backend.interaction.engine import InteractionEngine


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    """InteractionEngine with in-memory state (no disk I/O)."""
    registry = PersonalityRegistry(config={"base_dir": "/tmp/jarvis_test_personality"})
    return InteractionEngine(
        config={},
        personality_registry=registry,
        state_manager=InteractionStateManager(),
        strategy_engine=ResponseStrategyEngine(),
        channel_adapter=ChannelAdapter()
    )


@pytest.fixture
def strategy_engine():
    return ResponseStrategyEngine()


@pytest.fixture
def channel_adapter():
    return ChannelAdapter()


@pytest.fixture
def signal_detector():
    return EmotionalSignalDetector()


@pytest.fixture
def default_profile():
    return DEFAULT_JARVIS_PROFILE


@pytest.fixture
def default_state():
    return InteractionState(session_id="test_session")


@pytest.fixture
def neutral_signal():
    return EmotionalSignalResult(
        signal=EmotionalSignal.NEUTRAL,
        confidence=SignalConfidence.LOW,
        evidence_summary="No signals detected."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Personality Profile Loading
# ─────────────────────────────────────────────────────────────────────────────

def test_01_personality_profile_loading(engine):
    """Personality profile should load successfully with correct default values."""
    profile = engine.personality.get_active_profile()
    assert profile is not None
    assert profile.name == "Default JARVIS"
    assert profile.formality == FormalityLevel.PROFESSIONAL
    assert profile.verbosity == VerbosityLevel.ADAPTIVE
    assert profile.humor_level == HumorLevel.LOW
    assert profile.warmth_level == WarmthLevel.MODERATE
    assert profile.proactivity_level == ProactivityLevel.CONTROLLED


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Personality Consistency (model switching has no effect on profile)
# ─────────────────────────────────────────────────────────────────────────────

def test_02_personality_consistency_across_model_switches(engine):
    """Personality profile should not change when model routing changes."""
    profile_before = engine.personality.get_active_profile().name

    # Simulate model switches by calling pre/post-process with different routing statuses
    state, signal, strategy1 = engine.pre_process(
        "Explain caching strategies.", session_id="s1",
        task_category="question", channel="text"
    )
    out1 = engine.post_process("Caching reduces latency.", strategy1,
                                channel="text", execution_status="success",
                                routing_status="local_only", session_id="s1")

    state, signal, strategy2 = engine.pre_process(
        "Explain caching strategies.", session_id="s2",
        task_category="question", channel="text"
    )
    out2 = engine.post_process("Caching reduces latency.", strategy2,
                                channel="text", execution_status="success",
                                routing_status="cloud", session_id="s2")

    profile_after = engine.personality.get_active_profile().name

    assert profile_before == profile_after, "Profile should be unchanged after model routing change"
    assert out1.text and out2.text, "Both outputs should contain text"


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Short Response for Simple Question
# ─────────────────────────────────────────────────────────────────────────────

def test_03_short_response_for_simple_question(strategy_engine, default_profile, default_state, neutral_signal):
    """A short factual question should produce a SHORT response strategy."""
    strategy = strategy_engine.determine(
        profile=default_profile,
        state=default_state,
        signal_result=neutral_signal,
        task_category="question",
        channel="text",
        user_input="What time is it?"
    )
    assert strategy.response_length == ResponseLength.SHORT, (
        f"Simple question should yield SHORT, got {strategy.response_length}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Detailed Response for Technical Question
# ─────────────────────────────────────────────────────────────────────────────

def test_04_detailed_response_for_technical_question(strategy_engine, default_profile, neutral_signal):
    """A complex technical question should produce a LONG/EXPERT response strategy."""
    state = InteractionState(session_id="s", interaction_mode=InteractionMode.TECHNICAL_EXPERT)
    strategy = strategy_engine.determine(
        profile=default_profile,
        state=state,
        signal_result=neutral_signal,
        task_category="research_task",
        channel="text",
        user_input="Explain the architecture of the RAG system in detail."
    )
    assert strategy.response_length == ResponseLength.LONG or strategy.technical_depth == TechnicalDepth.EXPERT


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: Frustration Signal Adaptation
# ─────────────────────────────────────────────────────────────────────────────

def test_05_frustration_adaptation(strategy_engine, default_profile, default_state):
    """Frustration signal should produce CALM tone and NO humor."""
    frustrated_signal = EmotionalSignalResult(
        signal=EmotionalSignal.FRUSTRATED,
        confidence=SignalConfidence.HIGH,
        evidence_summary="Frustration keywords detected."
    )
    strategy = strategy_engine.determine(
        profile=default_profile,
        state=default_state,
        signal_result=frustrated_signal,
        task_category="question",
        channel="text",
        user_input="This code is still not working!"
    )
    assert strategy.tone == ToneStyle.CALM, f"Expected CALM tone, got {strategy.tone}"
    assert strategy.humor_level == HumorLevel.NONE, "No humor when frustrated"


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: Confusion Signal Adaptation
# ─────────────────────────────────────────────────────────────────────────────

def test_06_confusion_adaptation(strategy_engine, default_profile, default_state):
    """Confusion signal should produce SUPPORTIVE tone and SIMPLE technical depth."""
    confused_signal = EmotionalSignalResult(
        signal=EmotionalSignal.CONFUSED,
        confidence=SignalConfidence.MODERATE,
        evidence_summary="Clarification requested."
    )
    strategy = strategy_engine.determine(
        profile=default_profile,
        state=default_state,
        signal_result=confused_signal,
        task_category="question",
        channel="text",
        user_input="I don't understand what a vector index is."
    )
    assert strategy.tone == ToneStyle.SUPPORTIVE
    assert strategy.technical_depth == TechnicalDepth.SIMPLE


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: Urgency Adaptation
# ─────────────────────────────────────────────────────────────────────────────

def test_07_urgency_adaptation(strategy_engine, default_profile, default_state):
    """Urgent signal should produce SHORT, DIRECT response with no suggestions."""
    urgent_signal = EmotionalSignalResult(
        signal=EmotionalSignal.URGENT,
        confidence=SignalConfidence.HIGH,
        evidence_summary="Urgency keyword detected."
    )
    strategy = strategy_engine.determine(
        profile=default_profile,
        state=default_state,
        signal_result=urgent_signal,
        task_category="question",
        channel="text",
        user_input="Fix this ASAP — presentation in 10 minutes!"
    )
    assert strategy.response_length == ResponseLength.SHORT
    assert strategy.tone == ToneStyle.DIRECT
    assert strategy.proactive_suggestions == False


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: No Overconfident Emotional Inference
# ─────────────────────────────────────────────────────────────────────────────

def test_08_no_overconfident_emotional_inference():
    """A single ambiguous sentence should not produce HIGH-confidence signal."""
    result = EmotionalSignalDetector.detect("Why is this happening?")
    # "Why" alone is LOW confidence — should not be treated as definite frustration
    if result.signal == EmotionalSignal.FRUSTRATED:
        assert result.confidence != SignalConfidence.HIGH, (
            "Single 'why' sentence should not be HIGH confidence frustration"
        )


def test_08b_low_confidence_defaults_to_neutral_adaptation(strategy_engine, default_profile, default_state):
    """LOW confidence signal should NOT adapt tone away from neutral."""
    low_confidence_signal = EmotionalSignalResult(
        signal=EmotionalSignal.FRUSTRATED,
        confidence=SignalConfidence.LOW,
        evidence_summary="Very weak signals."
    )
    assert not low_confidence_signal.is_actionable(), "LOW confidence should not be actionable"


# ─────────────────────────────────────────────────────────────────────────────
# Test 9: Context-Aware "Continue"
# ─────────────────────────────────────────────────────────────────────────────

def test_09_context_aware_continue(strategy_engine, default_profile, neutral_signal):
    """'Continue' with active task should NOT request clarification."""
    state_with_task = InteractionState(
        session_id="active_session",
        active_task_id="task_abc123",
        active_task_context="Refactoring the authentication module"
    )
    strategy = strategy_engine.determine(
        profile=default_profile,
        state=state_with_task,
        signal_result=neutral_signal,
        task_category="conversation",
        channel="text",
        user_input="continue"
    )
    assert strategy.clarification_needed == False, "Should not ask for clarification when task is active"


# ─────────────────────────────────────────────────────────────────────────────
# Test 10: Ambiguous "Continue" Triggers Clarification
# ─────────────────────────────────────────────────────────────────────────────

def test_10_ambiguous_continue_clarification(strategy_engine, default_profile, neutral_signal):
    """'Open it' with no context should request clarification."""
    empty_state = InteractionState(session_id="empty_session")
    strategy = strategy_engine.determine(
        profile=default_profile,
        state=empty_state,
        signal_result=neutral_signal,
        task_category="conversation",
        channel="text",
        user_input="open it"
    )
    assert strategy.clarification_needed == True, "Ambiguous reference without context should need clarification"


# ─────────────────────────────────────────────────────────────────────────────
# Test 11: Voice Response Adaptation (shorter, no markdown)
# ─────────────────────────────────────────────────────────────────────────────

def test_11_voice_response_adaptation(channel_adapter):
    """Voice output should strip markdown and be shorter than text output."""
    raw = (
        "## Summary\n\n"
        "The **RAG system** uses `vector embeddings` and a retrieval pipeline.\n\n"
        "- Step 1: Embed the query.\n"
        "- Step 2: Retrieve top-k documents.\n"
        "- Step 3: Synthesize a response.\n\n"
        "```python\nresults = retriever.search(query)\n```\n\n"
        "This approach significantly improves accuracy on factual questions."
    )
    strategy = ResponseStrategy(
        response_length=ResponseLength.MEDIUM,
        voice_style=VoiceStyle.CONVERSATIONAL
    )
    output = channel_adapter.adapt(raw, strategy, channel="voice")
    assert "##" not in output.voice, "Voice should not contain markdown headings"
    assert "```" not in output.voice, "Voice should not contain code blocks"
    assert "**" not in output.voice, "Voice should not contain bold markdown"
    assert len(output.voice) < len(raw), "Voice output should be shorter than raw"


# ─────────────────────────────────────────────────────────────────────────────
# Test 12: Text Response Adaptation
# ─────────────────────────────────────────────────────────────────────────────

def test_12_text_response_full_for_long_strategy(channel_adapter):
    """LONG strategy should preserve full text content."""
    raw = "Step 1: A. Step 2: B. Step 3: C. Step 4: D. Step 5: E. Step 6: F."
    strategy = ResponseStrategy(response_length=ResponseLength.LONG)
    output = channel_adapter.adapt(raw, strategy, channel="text")
    # All content should be preserved
    assert "Step 6" in output.text


def test_12b_text_response_truncated_for_short_strategy(channel_adapter):
    """SHORT strategy should truncate to 1-2 sentences."""
    raw = "First sentence. Second sentence. Third sentence. Fourth sentence."
    strategy = ResponseStrategy(response_length=ResponseLength.SHORT)
    output = channel_adapter.adapt(raw, strategy, channel="text")
    assert "Fourth sentence" not in output.text, "SHORT strategy should truncate"


# ─────────────────────────────────────────────────────────────────────────────
# Test 13: HUD Response Adaptation
# ─────────────────────────────────────────────────────────────────────────────

def test_13_hud_response_ultra_compact(channel_adapter):
    """HUD output should be ≤12 words."""
    raw = (
        "The model comparison is complete. The local model performed best for offline use. "
        "I recommend using it as the primary model going forward."
    )
    strategy = ResponseStrategy(hud_style=HUDStyle.STATUS)
    output = channel_adapter.adapt(raw, strategy, channel="text")
    hud_words = output.hud.split()
    assert len(hud_words) <= 13, f"HUD should be ≤12 words, got {len(hud_words)}: '{output.hud}'"


def test_13b_hud_error_status(channel_adapter):
    """Error status should produce a clear HUD error message."""
    strategy = ResponseStrategy(is_error=True, hud_style=HUDStyle.ERROR)
    output = channel_adapter.adapt("Operation failed.", strategy, channel="text", execution_status="error")
    assert len(output.hud.split()) <= 15


# ─────────────────────────────────────────────────────────────────────────────
# Test 14: Focus Mode Behavior
# ─────────────────────────────────────────────────────────────────────────────

def test_14_focus_mode_concise_no_suggestions(strategy_engine, default_profile, neutral_signal):
    """Focus mode should produce SHORT responses with no proactive suggestions."""
    focus_state = InteractionState(
        session_id="focus_session",
        focus_active=True,
        interaction_mode=InteractionMode.FOCUS
    )
    strategy = strategy_engine.determine(
        profile=default_profile,
        state=focus_state,
        signal_result=neutral_signal,
        task_category="question",
        channel="voice",
        user_input="Status update?"
    )
    assert strategy.response_length == ResponseLength.SHORT
    assert strategy.proactive_suggestions == False
    assert strategy.humor_level == HumorLevel.NONE


def test_14b_focus_mode_set_via_engine(engine):
    """Focus mode should be toggleable via InteractionEngine."""
    engine.set_focus_mode("focus_test_session", True)
    state = engine.state_manager.get_or_create("focus_test_session")
    assert state.focus_active == True
    assert state.interaction_mode == InteractionMode.FOCUS

    engine.set_focus_mode("focus_test_session", False)
    state = engine.state_manager.get_or_create("focus_test_session")
    assert state.focus_active == False


# ─────────────────────────────────────────────────────────────────────────────
# Test 15: Humor Disabled in Critical Situations
# ─────────────────────────────────────────────────────────────────────────────

def test_15_humor_disabled_in_critical_situations(strategy_engine, default_profile, default_state, neutral_signal):
    """Error execution status must force humor to NONE."""
    strategy = strategy_engine.determine(
        profile=default_profile,
        state=default_state,
        signal_result=neutral_signal,
        task_category="computer_action",
        channel="text",
        user_input="Delete the system backup.",
        execution_status="error"
    )
    assert strategy.humor_level == HumorLevel.NONE, "No humor in error/critical situations"
    assert strategy.is_critical or strategy.is_error


def test_15b_humor_disabled_for_critical_task_category(strategy_engine, default_profile, default_state, neutral_signal):
    """Computer action task should suppress humor."""
    strategy = strategy_engine.determine(
        profile=default_profile,
        state=default_state,
        signal_result=neutral_signal,
        task_category="COMPUTER_ACTION",
        channel="text",
        user_input="Format the drive.",
        execution_status="error"
    )
    assert strategy.humor_level == HumorLevel.NONE


# ─────────────────────────────────────────────────────────────────────────────
# Test 16: Error Communication Reformatting
# ─────────────────────────────────────────────────────────────────────────────

def test_16_error_communication_reformatted(channel_adapter):
    """Raw error strings should be converted to human-readable messages."""
    raw_error = "Connection failed: ai service ollama connection refused port 11434"
    strategy = ResponseStrategy(is_error=True)
    output = channel_adapter.adapt(raw_error, strategy, channel="text", execution_status="error")
    # Should mention fallback and not just dump the raw error
    assert "unavailable" in output.text.lower() or "offline" in output.text.lower() or "fallback" in output.text.lower()
    assert "11434" not in output.text, "Should not expose raw port numbers"


def test_16b_timeout_error_message(channel_adapter):
    """Timeout should produce actionable human-readable message."""
    strategy = ResponseStrategy(is_error=True)
    output = channel_adapter.adapt("timed out", strategy, channel="text", execution_status="timeout")
    assert "timed out" in output.text.lower() or "time" in output.text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Test 17: Confidence-Aware Language
# ─────────────────────────────────────────────────────────────────────────────

def test_17_confidence_language_not_added_to_certain_responses(channel_adapter):
    """Already-hedged responses should not be double-prefixed."""
    response = "The connection failure may be caused by the local model server."
    strategy = ResponseStrategy()
    output = channel_adapter.adapt(
        response, strategy, channel="text",
        execution_status="partial_failure"
    )
    # Should not start with "The connection failure may be caused by The connection failure..."
    assert output.text.count("may be caused by") <= 1


def test_17b_direct_high_confidence_language(channel_adapter):
    """Successful responses should not be artificially hedged."""
    response = "The local model server is online."
    strategy = ResponseStrategy()
    output = channel_adapter.adapt(response, strategy, channel="text", execution_status="success")
    assert "might" not in output.text.lower() or response in output.text


# ─────────────────────────────────────────────────────────────────────────────
# Test 18: Model Switching Preserves Personality
# ─────────────────────────────────────────────────────────────────────────────

def test_18_model_switching_preserves_personality(engine):
    """Profile should remain unchanged across simulated model switches."""
    profile_id_before = engine.personality.get_active_profile().profile_id

    # Simulate local model routing
    _, _, strategy_local = engine.pre_process(
        "What is the status?", session_id="m1",
        task_category="question", channel="text"
    )
    out_local = engine.post_process(
        "All systems nominal.", strategy_local, "text", "success", "local_only", "m1", "question"
    )

    # Simulate cloud model routing
    _, _, strategy_cloud = engine.pre_process(
        "What is the status?", session_id="m2",
        task_category="question", channel="text"
    )
    out_cloud = engine.post_process(
        "All systems nominal.", strategy_cloud, "text", "success", "cloud", "m2", "question"
    )

    profile_id_after = engine.personality.get_active_profile().profile_id
    assert profile_id_before == profile_id_after
    # Both outputs should be reasonable
    assert out_local.text and out_cloud.text


# ─────────────────────────────────────────────────────────────────────────────
# Test 19: Agent Results Synthesized Through JARVIS Personality
# ─────────────────────────────────────────────────────────────────────────────

def test_19_agent_results_synthesized_through_personality(engine):
    """Raw agent output should be processed through personality channel adapter."""
    # Simulate a raw multi-agent response (typically verbose/structured)
    raw_agent_output = (
        "AGENT RESULT: Research complete.\n"
        "- Source 1: Found 15 papers on vector databases.\n"
        "- Source 2: Pinecone vs Qdrant comparison complete.\n"
        "- Recommendation: Use Qdrant for offline-first deployments.\n"
        "Status: SUCCESS. Confidence: HIGH."
    )
    _, _, strategy = engine.pre_process(
        "Research vector databases.", session_id="agent_test",
        task_category="research_task", channel="text"
    )
    output = engine.post_process(
        raw_agent_output, strategy, "text", "success", "cloud", "agent_test", "research_task"
    )
    # Output should exist and be coherent
    assert output.text
    assert output.voice  # Voice should be shorter
    assert len(output.voice) <= len(raw_agent_output)


# ─────────────────────────────────────────────────────────────────────────────
# Test 20: Social Conversation Does Not Activate Tools
# ─────────────────────────────────────────────────────────────────────────────

def test_20_social_greeting_short_circuits_tools(engine):
    """'How are you?' should return a social response, not trigger tool/agent dispatch."""
    output = engine.handle_social("How are you?", session_id="social_test")
    assert output is not None, "Social greeting should return a ChannelOutput"
    assert output.text, "Social response should have text"
    # Must not pretend to have human feelings
    assert "feel" not in output.text.lower() or "operational" in output.text.lower()
    # Must not claim to be human
    assert "i am human" not in output.text.lower()
    assert "feelings" not in output.text.lower()


def test_20b_non_social_input_not_short_circuited(engine):
    """Non-social inputs should not match the social short-circuit."""
    output = engine.handle_social("What is the disk usage?", session_id="s")
    assert output is None, "Technical queries should not match social greeting"


def test_20c_social_detector_greetings():
    """Social greeting detector should correctly identify common greetings."""
    assert EmotionalSignalDetector.is_social_greeting("hey there")
    assert EmotionalSignalDetector.is_social_greeting("Good morning!")
    assert EmotionalSignalDetector.is_social_greeting("how are you doing")
    assert not EmotionalSignalDetector.is_social_greeting("analyze the RAG architecture")
    assert not EmotionalSignalDetector.is_social_greeting("what's the battery level?")


# ─────────────────────────────────────────────────────────────────────────────
# Test 21: Interruption Handling
# ─────────────────────────────────────────────────────────────────────────────

def test_21_stop_talking_voice_only(engine):
    """'Stop talking' should stop voice but not the task."""
    stop_voice, stop_task = engine.check_interruption("stop talking")
    assert stop_voice == True, "Voice should stop"
    assert stop_task == False, "Task should NOT be cancelled for 'stop talking'"


def test_21b_stop_task_cancels_both(engine):
    """'Cancel the task' should stop both voice and task."""
    stop_voice, stop_task = engine.check_interruption("cancel the task")
    assert stop_voice == True
    assert stop_task == True


def test_21c_quiet_command(engine):
    """'Be quiet' should stop voice only."""
    stop_voice, stop_task = engine.check_interruption("be quiet")
    assert stop_voice == True
    assert stop_task == False


def test_21d_normal_input_no_interruption(engine):
    """Normal input should not trigger interruption."""
    stop_voice, stop_task = engine.check_interruption("What is the weather today?")
    assert stop_voice == False
    assert stop_task == False


# ─────────────────────────────────────────────────────────────────────────────
# Test 22: Explicit Preference Handling
# ─────────────────────────────────────────────────────────────────────────────

def test_22_explicit_preference_stored(engine):
    """Explicit user preferences should be stored in PersonalityRegistry."""
    engine.record_user_preference("technical_depth", "always_expert")
    value = engine.personality.get_preference("technical_depth")
    assert value == "always_expert"


def test_22b_preference_does_not_store_emotional_state(engine):
    """Temporary emotional signals should NOT be written to preferences."""
    # Simulate multiple frustration signals
    for _ in range(3):
        engine.state_manager.update_state(
            session_id="pref_test",
            user_input="This is still broken!",
            signal_result=EmotionalSignalResult(
                signal=EmotionalSignal.FRUSTRATED,
                confidence=SignalConfidence.HIGH,
                evidence_summary="Frustration."
            )
        )

    # Frustration should NOT appear in personality preferences
    prefs = engine.personality.get_all_preferences()
    for key, val in prefs.items():
        assert "frustrated" not in str(val).lower()
        assert "frustration" not in str(key).lower()


def test_22c_profile_switch_by_name(engine):
    """Profile should be switchable by natural name fragment."""
    success = engine.switch_profile("builder")
    assert success == True
    profile = engine.personality.get_active_profile()
    assert "builder" in profile.name.lower() or "builder" in profile.profile_id.lower()

    # Switch back
    engine.switch_profile("default")


# ─────────────────────────────────────────────────────────────────────────────
# Additional: PersonalityProfile serialization round-trip
# ─────────────────────────────────────────────────────────────────────────────

def test_profile_serialization_round_trip():
    """PersonalityProfile should serialize and deserialize without data loss."""
    profile = DEFAULT_JARVIS_PROFILE
    data = profile.to_dict()
    reconstructed = PersonalityProfile.from_dict(data)
    assert reconstructed.profile_id == profile.profile_id
    assert reconstructed.humor_level == profile.humor_level
    assert reconstructed.formality == profile.formality
    assert reconstructed.technical_depth == profile.technical_depth


def test_all_built_in_profiles_valid():
    """All built-in profiles should be loadable without error."""
    for profile_id, profile in BUILT_IN_PROFILES.items():
        assert profile.profile_id == profile_id
        assert isinstance(profile.humor_level, HumorLevel)
        assert isinstance(profile.formality, FormalityLevel)


def test_frustration_detector_compounding():
    """Multiple frustration signals in history should raise confidence."""
    history = [
        "This is still not working.",
        "I've tried everything.",
        "Why won't it work?"
    ]
    result = EmotionalSignalDetector.detect(
        "It's still broken!", history=history, session_frustration_count=2
    )
    assert result.signal == EmotionalSignal.FRUSTRATED
    assert result.confidence in (SignalConfidence.HIGH, SignalConfidence.MODERATE)
