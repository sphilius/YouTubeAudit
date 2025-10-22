#!/usr/bin/env python3
"""
YouTube Audit Engine - Interactive Launcher

Provides a friendly interface to choose between CLI and Web modes.
"""

import os
import sys
import subprocess
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich import print as rprint

console = Console()


def check_backend_running() -> bool:
    """Check if backend is already running."""
    import requests
    try:
        response = requests.get('http://localhost:8000/', timeout=2)
        return response.status_code == 200
    except:
        return False


def start_backend() -> subprocess.Popen:
    """Start the backend server in background."""
    console.print("[cyan]Starting backend server...[/cyan]")

    # Set PYTHONPATH
    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path.cwd())

    # Start backend
    backend_process = subprocess.Popen(
        [sys.executable, 'backend/main.py'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait a bit for startup
    import time
    time.sleep(3)

    if check_backend_running():
        console.print("[green]✓ Backend started successfully[/green]")
        return backend_process
    else:
        console.print("[yellow]⚠ Backend may still be starting...[/yellow]")
        return backend_process


def launch_cli():
    """Launch CLI interface."""
    console.clear()
    console.print(Panel.fit(
        "[bold cyan]YouTube Audit Engine - CLI Mode[/bold cyan]\n"
        "Command-line interface for analyzing YouTube watch history",
        title="🎬 CLI Mode"
    ))

    # Check if backend is running
    if not check_backend_running():
        console.print("\n[yellow]Backend is not running.[/yellow]")
        start_now = Prompt.ask(
            "Start backend automatically?",
            choices=["yes", "no"],
            default="yes"
        )

        if start_now == "yes":
            backend_process = start_backend()
        else:
            console.print("\n[yellow]Please start the backend manually:[/yellow]")
            console.print("  python backend/main.py")
            console.print("\nThen restart this launcher.")
            return

    # Run CLI
    console.print("\n[cyan]Launching CLI interface...[/cyan]\n")
    from cli.interface import main as cli_main
    cli_main()


def launch_web():
    """Launch web interface."""
    console.clear()
    console.print(Panel.fit(
        "[bold cyan]YouTube Audit Engine - Web Mode[/bold cyan]\n"
        "Browser-based interface powered by Streamlit",
        title="🌐 Web Mode"
    ))

    # Check if backend is running
    backend_process = None
    if not check_backend_running():
        console.print("\n[yellow]Backend is not running.[/yellow]")
        start_now = Prompt.ask(
            "Start backend automatically?",
            choices=["yes", "no"],
            default="yes"
        )

        if start_now == "yes":
            backend_process = start_backend()
        else:
            console.print("\n[yellow]Please start the backend manually:[/yellow]")
            console.print("  python backend/main.py")
            return

    # Launch Streamlit
    console.print("\n[cyan]Launching Streamlit web interface...[/cyan]")
    console.print("[dim]The web interface will open in your browser.[/dim]\n")

    try:
        subprocess.run(
            ['streamlit', 'run', 'frontend/app.py'],
            check=True
        )
    except KeyboardInterrupt:
        console.print("\n[cyan]Web interface stopped[/cyan]")
    finally:
        if backend_process:
            console.print("[cyan]Stopping backend server...[/cyan]")
            backend_process.terminate()


def show_main_menu():
    """Display main menu and handle selection."""
    console.clear()

    # ASCII art banner
    banner = """
[bold cyan]
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     🎬  YouTube Audit Engine                             ║
║                                                           ║
║     Analyze your YouTube watch history                   ║
║     Discover patterns, clusters, and insights            ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
[/bold cyan]
"""

    console.print(banner)
    console.print("[bold]Choose your interface:[/bold]\n")
    console.print("  [cyan]1[/cyan]. CLI Mode     - Command-line interface (terminal-based)")
    console.print("  [cyan]2[/cyan]. Web Mode     - Browser-based interface (Streamlit)")
    console.print("  [cyan]3[/cyan]. Help         - Setup and usage information")
    console.print("  [cyan]4[/cyan]. Exit\n")

    choice = Prompt.ask(
        "Select mode",
        choices=["1", "2", "3", "4"],
        default="2"
    )

    return choice


def show_help():
    """Display help information."""
    console.clear()
    help_text = """
[bold cyan]YouTube Audit Engine - Help[/bold cyan]

[bold]Getting Started:[/bold]

1. Make sure you have a .env file with your configuration:
   - GOOGLE_API_KEY (required for metadata enrichment)
   - DATABASE_URL (PostgreSQL connection)
   - REDIS_URL (Redis connection)
   - API_BEARER_TOKEN (for API authentication)

2. Install dependencies:
   [dim]pip install -r requirements.txt[/dim]

3. Start required services (if not using Docker):
   - PostgreSQL database
   - Redis server

[bold]CLI Mode:[/bold]
- Terminal-based interface
- Perfect for automation and scripting
- Can be used without a web browser
- Supports batch processing

  Usage:
    [dim]python -m cli.interface watch-history.json[/dim]
    [dim]python -m cli.interface --interactive[/dim]

[bold]Web Mode:[/bold]
- Browser-based interface using Streamlit
- Rich visualizations and charts
- Interactive data exploration
- User-friendly for non-technical users

  Access at: http://localhost:8501

[bold]Direct Backend API:[/bold]
- RESTful API at http://localhost:8000
- OpenAPI docs at http://localhost:8000/docs
- Can be integrated with other tools

[bold]Windows Users:[/bold]
See WINDOWS_SETUP.md for platform-specific instructions.

[bold]Documentation:[/bold]
- README.md - Overview and features
- ARCHITECTURE.md - System design
- FEATURE_RECOMMENDATIONS.md - Roadmap
- IMPLEMENTATION_TASKS.md - Development tasks

[bold]Troubleshooting:[/bold]
- Backend not starting: Check logs in console
- Database errors: Verify DATABASE_URL in .env
- Redis errors: Ensure Redis is running
- API quota exceeded: Wait 24 hours or use different API key

For more help, visit: https://github.com/yourusername/YouTubeAudit
"""

    console.print(Panel(help_text, title="📚 Help & Documentation", border_style="cyan"))
    console.print()
    input("Press Enter to return to main menu...")


def main():
    """Main launcher function."""
    try:
        while True:
            choice = show_main_menu()

            if choice == "1":
                launch_cli()
            elif choice == "2":
                launch_web()
            elif choice == "3":
                show_help()
            elif choice == "4":
                console.print("\n[cyan]Thank you for using YouTube Audit Engine![/cyan]")
                console.print("[dim]Star us on GitHub if you found this useful 🌟[/dim]\n")
                break

    except KeyboardInterrupt:
        console.print("\n\n[cyan]Goodbye![/cyan]")
        sys.exit(0)


if __name__ == '__main__':
    main()
