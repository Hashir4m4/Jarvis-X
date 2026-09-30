import argparse
import asyncio
import logging
import sys
import os

# Ensure project root is on the path when run as a subprocess
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import uvicorn
from backend.config import get_config, ConfigValidator, generate_startup_banner
from backend.core.core import JarvisCore
from backend.core.models import UserInput, InputChannel
from backend.api import server

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Jarvis X OS Main Entry Point")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode without the web dashboard")
    parser.add_argument("--env", type=str, default=None, help="Environment profile (development, testing, production)")
    parser.add_argument("--mode", type=str, default=None, help="Operating mode (offline, online, hybrid)")
    args = parser.parse_args()

    # 1. Load centralized configuration
    config_obj = get_config(profile=args.env, mode=args.mode)

    # 2. Validate configuration before booting subsystems
    ConfigValidator.validate_or_raise(config_obj)

    # 3. Print secret-safe startup banner
    print(generate_startup_banner(config_obj))

    # 4. Initialize Core with backward-compatible configuration dictionary
    config_dict = config_obj.to_legacy_dict()
    core = JarvisCore(config_dict)

    if args.cli:
        # CLI Mode powered by JARVIS Core
        logger.info("Starting Jarvis OS in CLI mode...")
        print("Jarvis OS Online. Type 'quit' to exit.")

        async def run_cli():
            await core.start()
            while True:
                try:
                    user_text = input("\nYou: ")
                    if user_text.strip().lower() in ("quit", "exit"):
                        break

                    user_input = UserInput(content=user_text, channel=InputChannel.TEXT)
                    print("Jarvis: ", end="", flush=True)

                    async for event in core.process_stream(user_input):
                        if event.get("type") == "chat_stream":
                            print(event.get("data", {}).get("chunk", ""), end="", flush=True)
                    print()
                except (KeyboardInterrupt, EOFError):
                    break
            await core.stop()
            print("\nJarvis OS shut down.")

        asyncio.run(run_cli())
    else:
        # Start the FastAPI Web Server with JARVIS Core
        logger.info("Starting Jarvis OS Web Dashboard...")
        server.jarvis_core = core
        server.jarvis_brain = core.brain
        host = config_obj.network.backend_host
        port = config_obj.network.backend_port
        logger.info(f"Binding API server to {host}:{port}")
        uvicorn.run(server.app, host=host, port=port, log_level=config_obj.logging.level.lower())


if __name__ == "__main__":
    main()
