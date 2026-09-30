from .schema import JarvisConfig


def generate_startup_banner(config: JarvisConfig) -> str:
    """
    Generates a clean, professional startup telemetry summary for JARVIS X.
    Guarantees secrets/API keys are masked or omitted entirely.
    """
    env = config.environment
    net = config.network
    feat = config.features
    local_ai = config.local_ai
    cloud_ai = config.cloud_ai

    cloud_status = "ENABLED" if (feat.cloud_ai_enabled and cloud_ai.has_any_credentials()) else "DISABLED"
    cloud_providers = []
    if cloud_ai.openai_api_key:
        cloud_providers.append("OpenAI")
    if cloud_ai.anthropic_api_key:
        cloud_providers.append("Anthropic")
    if cloud_ai.gemini_api_key:
        cloud_providers.append("Gemini")
    if cloud_ai.groq_api_key:
        cloud_providers.append("Groq")
    cloud_detail = f"({', '.join(cloud_providers)})" if cloud_providers else "([NONE CONFIGURED])"

    banner = [
        "============================================================",
        "                     JARVIS X OS v2.0                       ",
        "============================================================",
        f"  Environment Profile : {env.profile.value.upper()}",
        f"  Operating Mode      : {env.mode.value.upper()}",
        f"  Local AI Engine     : {'ENABLED' if feat.local_ai_enabled else 'DISABLED'} ({local_ai.provider.title()} @ {local_ai.base_url}, {local_ai.default_model})",
        f"  Cloud AI Providers  : {cloud_status} {cloud_detail}",
        f"  Backend Endpoint    : http://{net.backend_host}:{net.backend_port}",
        f"  HUD Frontend Port   : {net.frontend_port}",
        f"  Voice Subsystem     : {'ENABLED' if feat.voice_enabled else 'DISABLED'} ({config.voice.stt_engine} / {config.voice.wake_word})",
        f"  Vision Subsystem    : {'ENABLED' if feat.vision_enabled else 'DISABLED'} ({config.vision.target_fps} FPS)",
        f"  Memory & Vault      : {'ENABLED' if feat.memory_enabled else 'DISABLED'} (SQLite + Chroma)",
        f"  Automation Control  : {'ENABLED' if feat.automation_enabled else 'DISABLED'} (SecurityProxy Active)",
        f"  Self-Diagnostics    : {'ENABLED' if feat.diagnostics_enabled else 'DISABLED'}",
        "============================================================",
    ]
    return "\n".join(banner)
