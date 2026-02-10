"""
SOVRA: A Sovereign & Self-Evolving AI Agent
Main entry point — boots up all systems and runs the agent.

Usage:
    python -m src.main
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.logging import RichHandler

# Load environment
load_dotenv()

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
log_file = os.getenv("LOG_FILE", "./data/logs/sovra.log")
Path(log_file).parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(message)s",
    datefmt="[%X]",
    handlers=[
        RichHandler(rich_tracebacks=True, show_path=False),
        logging.FileHandler(log_file, encoding="utf-8"),
    ],
)
logger = logging.getLogger("sovra")

console = Console()


async def main():
    """Main entry point for SOVRA."""
    console.print(
        Panel.fit(
            "[bold cyan]SOVRA: A Sovereign & Self-Evolving AI Agent[/]\n"
            "[dim]Keep your data, evolve your soul.[/]\n"
            "[dim]A privacy-first autonomous agent powered by Local LLM and OpenClaw.[/]",
            border_style="cyan",
        )
    )

    # Import bridge (after env is loaded)
    from .gateway.openclaw_bridge import OpenClawBridge

    bridge = OpenClawBridge()

    # Handle graceful shutdown
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()

    def handle_signal():
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    try:
        # Start all subsystems
        await bridge.start()

        # Print status
        status = bridge.get_status()
        console.print(f"\n[green]✅ SOVRA is running![/]")
        console.print(f"   [cyan]Name:[/] {status['name']}")
        console.print(f"   [cyan]Autonomy:[/] {status['autonomy_level']}")
        console.print(f"   [cyan]Memories:[/] {status['memory']['long_term_count']}")
        console.print(f"   [cyan]Interactions:[/] {status['interactions']['total']}")
        # Detect if running interactively (TTY) or as daemon (backgrounded)
        is_interactive = sys.stdin.isatty()

        if is_interactive:
            console.print(f"\n[dim]SOVRA is now autonomous. It will process tasks, learn, and evolve.[/]")
            console.print(f"[dim]Type a message to chat, '/status' for status, 'quit' to exit.[/]\n")

            # Interactive shell for direct testing
            while not shutdown_event.is_set():
                try:
                    user_input = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: input("You: ")
                    )
                    if not user_input.strip():
                        continue
                    if user_input.strip().lower() in ("quit", "exit", "bye"):
                        break
                    if user_input.strip().lower() == "/status":
                        status = bridge.get_status()
                        console.print_json(data=status)
                        continue

                    response = await bridge.handle_message(user_input, platform="cli")
                    console.print(f"[cyan]Sovra:[/] {response}\n")

                except EOFError:
                    break
                except KeyboardInterrupt:
                    break
        else:
            # Daemon mode — no interactive input, just keep running
            console.print(f"\n[dim]SOVRA running in daemon mode. Connect via OpenClaw.[/]")
            await shutdown_event.wait()

    except ConnectionError as e:
        console.print(f"[red]❌ {e}[/]")
        console.print("[yellow]Make sure Ollama is running: sudo systemctl start ollama[/]")
        sys.exit(1)
    finally:
        await bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())
