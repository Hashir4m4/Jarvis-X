"""
JARVIS Emotional Signal Detector

Performs lightweight, cautious, lexical-heuristic-based detection of
communication signals from user input.

CRITICAL DESIGN CONSTRAINTS:
- Uses keyword/phrase matching ONLY. No LLM required.
- Assigns confidence: HIGH, MODERATE, or LOW.
- LOW-confidence signals default to NEUTRAL for tone decisions.
- Evidence is always summarized in EmotionalSignalResult.
- Never diagnoses psychological states, mental health, or personality.
- Never presents a guess as a fact.
- One sentence is NEVER sufficient evidence for HIGH confidence.
"""
import re
import logging
from typing import List, Optional, Tuple, Dict, Any

from .models import EmotionalSignal, SignalConfidence, EmotionalSignalResult

logger = logging.getLogger("JARVIS.SignalDetector")


# ─────────────────────────────────────────────────────────────────────────────
# Detection Lexicons
# Each entry: (pattern, weight, signal, description)
# Higher weight = stronger evidence. Multiple hits raise confidence.
# ─────────────────────────────────────────────────────────────────────────────

_FRUSTRATION_PATTERNS: List[Tuple[str, int, str]] = [
    (r"\b(still\s+(not\s+)?working|still\s+broken|still\s+failing)\b", 3, "persistent failure"),
    (r"\b(why\s+is\s+this|why\s+won'?t|why\s+can'?t)\b", 2, "rhetorical 'why'"),
    (r"\b(driving\s+me\s+crazy|so\s+annoying|this\s+is\s+ridiculous)\b", 3, "frustration expression"),
    (r"\b(again|keeps?\s+(failing|breaking|crashing))\b", 2, "repeated failure"),
    (r"\b(useless|broken|terrible|awful|horrible)\b", 2, "negative evaluation"),
    (r"\b(argh|ugh|damn|dammit|wtf)\b", 2, "emotional expletive"),
    (r"!{2,}", 1, "multiple exclamation marks"),
    (r"\b(i'?ve\s+tried\s+everything|nothing\s+works)\b", 3, "exhaustion statement"),
]

_CONFUSION_PATTERNS: List[Tuple[str, int, str]] = [
    (r"\b(i\s+don'?t\s+(understand|get|follow|know\s+what))\b", 3, "explicit confusion"),
    (r"\b(what\s+does\s+that\s+mean|what\s+is\s+that)\b", 2, "definition request"),
    (r"\b(confused|lost|unclear|not\s+sure\s+what)\b", 2, "confusion indicator"),
    (r"\b(can\s+you\s+(explain|clarify|elaborate|simplify))\b", 2, "clarification request"),
    (r"\b(huh|wait,?\s+what|sorry,?\s+what)\b", 2, "comprehension check"),
    (r"\b(doesn'?t\s+make\s+sense|makes\s+no\s+sense)\b", 3, "sense-making failure"),
    (r"\?{2,}", 1, "multiple question marks"),
]

_EXCITED_PATTERNS: List[Tuple[str, int, str]] = [
    (r"\b(amazing|awesome|brilliant|excellent|fantastic|great|incredible|perfect|wow)\b", 2, "positive superlative"),
    (r"\b(love\s+this|love\s+it|this\s+is\s+great|yes!)\b", 2, "enthusiasm expression"),
    (r"\b(can'?t\s+wait|so\s+excited|really\s+excited)\b", 3, "explicit excitement"),
    (r"!{1,}", 1, "exclamation"),  # Lower weight, needs corroboration
    (r"\b(let'?s\s+go|let'?s\s+do\s+this|let'?s\s+build)\b", 2, "action enthusiasm"),
]

_URGENT_PATTERNS: List[Tuple[str, int, str]] = [
    (r"\b(asap|as\s+soon\s+as\s+possible|right\s+now|immediately|urgent)\b", 3, "urgency keyword"),
    (r"\b(emergency|critical|deadline|due\s+in|presentation\s+in)\b", 3, "deadline/emergency"),
    (r"\b(hurry|quickly|fast|need\s+this\s+now|need\s+it\s+now)\b", 2, "speed request"),
    (r"\b(can\s+you\s+do\s+this\s+fast|no\s+time\s+to\s+explain)\b", 2, "time pressure"),
]

_FOCUSED_PATTERNS: List[Tuple[str, int, str]] = [
    (r"\b(just\s+(do|give|show|tell)|only\s+(the|show))\b", 2, "filtering request"),
    (r"\b(no\s+explanations?|skip\s+the\s+details|don'?t\s+elaborate)\b", 3, "brevity request"),
    (r"\b(focus\s+mode|focus\s+on|stay\s+focused)\b", 3, "explicit focus"),
    (r"\b(short\s+answer|quick\s+answer|brief\s+answer)\b", 2, "brevity request"),
]

_UNSURE_PATTERNS: List[Tuple[str, int, str]] = [
    (r"\b(maybe|perhaps|possibly|i\s+think|not\s+sure)\b", 2, "uncertainty qualifier"),
    (r"\b(could\s+be|might\s+be|seems\s+like|looks\s+like)\b", 1, "hedged statement"),
    (r"\b(i\s+guess|sort\s+of|kind\s+of|more\s+or\s+less)\b", 1, "vague qualifier"),
    (r"\b(not\s+really\s+sure|don'?t\s+know\s+if)\b", 2, "explicit uncertainty"),
]

_ALL_DETECTORS: Dict[EmotionalSignal, List[Tuple[str, int, str]]] = {
    EmotionalSignal.FRUSTRATED: _FRUSTRATION_PATTERNS,
    EmotionalSignal.CONFUSED: _CONFUSION_PATTERNS,
    EmotionalSignal.EXCITED: _EXCITED_PATTERNS,
    EmotionalSignal.URGENT: _URGENT_PATTERNS,
    EmotionalSignal.FOCUSED: _FOCUSED_PATTERNS,
    EmotionalSignal.UNSURE: _UNSURE_PATTERNS,
}

# Thresholds: total weight needed to reach each confidence level
_CONFIDENCE_THRESHOLDS = {
    SignalConfidence.HIGH: 5,
    SignalConfidence.MODERATE: 3,
    SignalConfidence.LOW: 1,
}


# ─────────────────────────────────────────────────────────────────────────────
# Detector Class
# ─────────────────────────────────────────────────────────────────────────────

class EmotionalSignalDetector:
    """
    Lightweight, evidence-based communication signal detector.

    Uses lexical heuristics only — no LLM inference, no cloud calls.
    Confidence is always calculated and exposed in results.

    Design: Does NOT fire on a single data point. A single frustrated sentence
    produces LOW confidence → defaults to NEUTRAL for tone adaptation.
    Repeated signals within the same context window compound evidence.
    """

    @staticmethod
    def detect(
        user_input: str,
        history: Optional[List[str]] = None,
        session_frustration_count: int = 0
    ) -> EmotionalSignalResult:
        """
        Analyzes user_input for communication signals.

        Args:
            user_input: The current user message.
            history: Optional recent conversation turns (last 3–5) for context.
            session_frustration_count: Accumulated frustration signals this session.

        Returns:
            EmotionalSignalResult with signal, confidence, and evidence.
        """
        lower = user_input.strip().lower()
        history = history or []

        scores: Dict[EmotionalSignal, int] = {sig: 0 for sig in EmotionalSignal}
        indicators: Dict[EmotionalSignal, List[str]] = {sig: [] for sig in EmotionalSignal}

        # Score current input
        for signal, patterns in _ALL_DETECTORS.items():
            for pattern, weight, description in patterns:
                if re.search(pattern, lower, re.IGNORECASE):
                    scores[signal] += weight
                    indicators[signal].append(description)

        # History context: add partial weight from recent turns
        for past_turn in history[-3:]:
            past_lower = past_turn.strip().lower()
            for signal, patterns in _ALL_DETECTORS.items():
                for pattern, weight, description in patterns:
                    if re.search(pattern, past_lower, re.IGNORECASE):
                        scores[signal] += max(1, weight // 2)  # Discounted evidence

        # Session compound: repeated frustration in session boosts score
        if session_frustration_count >= 2:
            scores[EmotionalSignal.FRUSTRATED] += 2

        # Find winning signal
        dominant_signal = EmotionalSignal.NEUTRAL
        dominant_score = 0
        for signal, score in scores.items():
            if score > dominant_score:
                dominant_score = score
                dominant_signal = signal

        # Determine confidence
        if dominant_signal == EmotionalSignal.NEUTRAL or dominant_score == 0:
            confidence = SignalConfidence.LOW
        elif dominant_score >= _CONFIDENCE_THRESHOLDS[SignalConfidence.HIGH]:
            confidence = SignalConfidence.HIGH
        elif dominant_score >= _CONFIDENCE_THRESHOLDS[SignalConfidence.MODERATE]:
            confidence = SignalConfidence.MODERATE
        else:
            confidence = SignalConfidence.LOW

        # Build evidence summary
        raw_indicators = indicators.get(dominant_signal, [])
        if not raw_indicators or dominant_signal == EmotionalSignal.NEUTRAL:
            evidence_summary = "No strong signals detected; defaulting to neutral."
        else:
            evidence_summary = (
                f"Signal '{dominant_signal.value}' detected "
                f"(score={dominant_score}, confidence={confidence.value}): "
                + ", ".join(raw_indicators[:3])
            )

        logger.debug(f"[SignalDetector] '{user_input[:60]}' → {dominant_signal.value} "
                     f"(score={dominant_score}, conf={confidence.value})")

        return EmotionalSignalResult(
            signal=dominant_signal,
            confidence=confidence,
            evidence_summary=evidence_summary,
            raw_indicators=raw_indicators
        )

    @staticmethod
    def is_social_greeting(user_input: str) -> bool:
        """
        Detects casual social conversation that should NOT activate tools.

        Examples: "how are you", "hey", "what's up", "good morning"
        """
        social_patterns = [
            r"^(hi|hey|hello|yo|howdy|sup|hiya)\b",
            r"^how\s+are\s+you",
            r"^what'?s\s+up",
            r"^good\s+(morning|afternoon|evening|night)\b",
            r"^how'?s\s+it\s+going",
            r"^how\s+do\s+you\s+do",
            r"^nice\s+to\s+(meet|see)\s+you",
        ]
        lower = user_input.strip().lower()
        return any(re.search(p, lower) for p in social_patterns)

    @staticmethod
    def is_interruption_command(user_input: str) -> Tuple[bool, bool]:
        """
        Detects voice/task interruption intent.

        Returns:
            (stop_voice: bool, stop_task: bool)
            - stop_voice=True, stop_task=False → "stop talking"
            - stop_voice=True, stop_task=True  → "stop the task"
        """
        lower = user_input.strip().lower()

        # Task cancellation (stronger intent)
        task_stop = bool(re.search(
            r"\b(stop\s+the\s+task|cancel\s+(the\s+)?task|abort|cancel\s+that|stop\s+everything)\b",
            lower
        ))

        # Voice-only stop
        voice_stop = bool(re.search(
            r"\b(stop\s+talking|shut\s+up|stop\s+speaking|be\s+quiet|enough)\b",
            lower
        )) or task_stop  # Task stop implies voice stop too

        return voice_stop, task_stop


