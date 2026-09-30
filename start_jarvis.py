import subprocess
import time
import sys
import os
import signal
import socket
import logging
import argparse
from urllib.parse import urlparse

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.config import get_config, ConfigValidator, generate_startup_banner

logging.basicConfig(level=logging.INFO, format="%(asctime)s - JARVIS BOOT - %(message)s")
logger = logging.getLogger(__name__)

# Track child processes for clean shutdown
processes = []


def check_port(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is in use."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def cleanup(signum=None, frame=None):
    logger.info("Initiating shutdown sequence...")
    for p in processes:
        try:
            p.terminate()
            p.wait(timeout=3)
        except Exception as e:
            logger.warning(f"Failed to terminate process {getattr(p, 'pid', 'unknown')}: {e}")
            try:
                p.kill()
            except Exception:
                pass
    logger.info("Jarvis OS offline.")
    sys.exit(0)


# Register shutdown handlers
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def main():
    parser = argparse.ArgumentParser(description="JARVIS X Unified Launcher")
    parser.add_argument("--env", type=str, default=None, help="Environment profile (development, testing, production)")
    parser.add_argument("--mode", type=str, default=None, help="Operating mode (offline, online, hybrid)")
    parser.add_argument("--no-frontend", action="store_true", help="Do not launch React/Electron HUD")
    args = parser.parse_args()

    # 1. Load & Validate Configuration
    config = get_config(profile=args.env, mode=args.mode)
    validation = ConfigValidator.validate(config)
    if not validation.is_valid:
        logger.error("Configuration validation failed:\n  " + "\n  ".join(validation.errors))
        sys.exit(1)

    for w in validation.warnings:
        logger.warning(f"[CONFIG WARNING] {w}")

    # 2. Print Startup Banner
    print(generate_startup_banner(config))

    # 3. Check AI Engine (Ollama / Local Provider)
    ollama_parsed = urlparse(config.network.ollama_url)
    ollama_host = ollama_parsed.hostname or "127.0.0.1"
    ollama_port = ollama_parsed.port or 11434

    logger.info(f"Checking Local AI Engine ({config.local_ai.provider.title()} @ {ollama_host}:{ollama_port})...")
    if not check_port(ollama_port, ollama_host):
        if config.environment.mode.value == "offline":
            logger.warning(
                f"[OFFLINE MODE] Local AI engine not detected on {ollama_host}:{ollama_port}. "
                "JARVIS will operate in deterministic local skill mode without neural generation."
            )
        else:
            logger.warning(
                f"Local AI engine not detected on {ollama_host}:{ollama_port}. "
                "Local inference unavailable; requests will route to cloud providers or fallback skills."
            )
    else:
        logger.info(f"[OK] Local {config.local_ai.provider.title()} AI Engine online.")

    # Pass configuration to subprocesses via environment
    child_env = os.environ.copy()
    child_env["FASTAPI_HOST"] = str(config.network.backend_host)
    child_env["FASTAPI_PORT"] = str(config.network.backend_port)
    child_env["HUD_PORT"] = str(config.network.frontend_port)
    child_env["HUD_URL"] = str(config.network.frontend_url)
    child_env["JARVIS_ENV"] = str(config.environment.profile.value)
    child_env["JARVIS_MODE"] = str(config.environment.mode.value)

    # 4. Start Frontend (React/Vite) & Electron Desktop Overlay
    if not args.no_frontend:
        frontend_dir = str(config.paths.resolve("frontend"))
        if os.path.exists(frontend_dir):
            logger.info(f"Booting HUD (React Frontend on port {config.network.frontend_port})...")
            frontend_proc = subprocess.Popen(
                "npm run dev",
                cwd=frontend_dir,
                shell=True,
                env=child_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            processes.append(frontend_proc)
            logger.info("[OK] HUD booting in background.")

            logger.info("Launching Desktop Floating Shell (Electron)...")
            electron_proc = subprocess.Popen(
                "npm run electron",
                cwd=frontend_dir,
                shell=True,
                env=child_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            processes.append(electron_proc)
            logger.info("[OK] Desktop App floating on screen.")
        else:
            logger.warning("Frontend directory not found. Skipping HUD.")

    # 5. Start Backend (FastAPI Core)
    logger.info(f"Booting Brain (FastAPI Backend on http://{config.network.backend_host}:{config.network.backend_port})...")
    time.sleep(1)  # Allow frontend a second to start
    backend_cmd = [sys.executable, "backend/main.py"]
    if args.env:
        backend_cmd.extend(["--env", args.env])
    if args.mode:
        backend_cmd.extend(["--mode", args.mode])

    backend_proc = subprocess.Popen(
        backend_cmd,
        env=child_env,
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    processes.append(backend_proc)

    logger.info("\nALL SYSTEMS GO. Press Ctrl+C to shutdown.")

    # Wait for backend to exit
    try:
        backend_proc.wait()
    except KeyboardInterrupt:
        cleanup()

    cleanup()


if __name__ == "__main__":
    main()
