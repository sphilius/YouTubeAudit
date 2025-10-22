"""
CLI Interface for YouTube Audit Engine.

Provides a command-line interface for interacting with the YouTube Audit backend
without requiring a web browser.
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import print as rprint

console = Console()


class YouTubeAuditCLI:
    """Command-line interface for YouTube Audit Engine."""

    def __init__(self, api_url: str = "http://localhost:8000", api_token: Optional[str] = None):
        """
        Initialize CLI client.

        Args:
            api_url: Backend API URL
            api_token: Bearer token for authentication
        """
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token or os.getenv('API_BEARER_TOKEN', 'dev-token-12345678')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_token}'
        })

    def check_health(self) -> bool:
        """
        Check if backend is healthy and reachable.

        Returns:
            True if backend is healthy, False otherwise
        """
        try:
            response = self.session.get(f'{self.api_url}/')
            if response.status_code == 200:
                data = response.json()
                console.print(f"[green]✓ Backend is healthy[/green]")
                console.print(f"  Status: {data.get('status', 'unknown')}")
                console.print(f"  Message: {data.get('message', '')}")
                return True
            else:
                console.print(f"[red]✗ Backend returned status code {response.status_code}[/red]")
                return False
        except requests.exceptions.ConnectionError:
            console.print(f"[red]✗ Cannot connect to backend at {self.api_url}[/red]")
            console.print("[yellow]Make sure the backend is running:[/yellow]")
            console.print("  python backend/main.py")
            return False
        except Exception as e:
            console.print(f"[red]✗ Error checking backend health: {e}[/red]")
            return False

    def analyze_watch_history(
        self,
        file_path: str,
        google_api_key: Optional[str] = None,
        poll_interval: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze YouTube watch history from a JSON file.

        Args:
            file_path: Path to watch-history.json
            google_api_key: Google API key for YouTube Data API
            poll_interval: Seconds between status polls

        Returns:
            Analysis results or None if failed
        """
        # Validate file exists
        if not Path(file_path).exists():
            console.print(f"[red]✗ File not found: {file_path}[/red]")
            return None

        # Get API key if not provided
        if not google_api_key:
            google_api_key = os.getenv('GOOGLE_API_KEY')
            if not google_api_key:
                google_api_key = Prompt.ask(
                    "[yellow]Enter your Google API Key[/yellow]",
                    password=True
                )

        console.print(f"\n[cyan]Uploading watch history file...[/cyan]")

        try:
            # Upload file and start analysis
            with open(file_path, 'rb') as f:
                files = {'file': (Path(file_path).name, f, 'application/json')}
                data = {'api_key': google_api_key} if google_api_key else {}

                response = self.session.post(
                    f'{self.api_url}/analyze',
                    files=files,
                    data=data
                )

            if response.status_code != 202:
                console.print(f"[red]✗ Upload failed: {response.status_code}[/red]")
                console.print(response.text)
                return None

            result = response.json()
            task_id = result.get('task_id')

            console.print(f"[green]✓ Analysis started[/green]")
            console.print(f"  Task ID: {task_id}")

            # Poll for results
            return self._poll_task_status(task_id, poll_interval)

        except Exception as e:
            console.print(f"[red]✗ Error during analysis: {e}[/red]")
            return None

    def _poll_task_status(self, task_id: str, poll_interval: int) -> Optional[Dict[str, Any]]:
        """
        Poll task status until completion.

        Args:
            task_id: Celery task ID
            poll_interval: Seconds between polls

        Returns:
            Task result or None if failed
        """
        console.print(f"\n[cyan]Processing analysis (this may take several minutes)...[/cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Analyzing watch history...", total=None)

            while True:
                try:
                    response = self.session.get(f'{self.api_url}/status/{task_id}')

                    if response.status_code != 200:
                        console.print(f"[red]✗ Status check failed: {response.status_code}[/red]")
                        return None

                    status_data = response.json()
                    state = status_data.get('state')

                    if state == 'PENDING':
                        progress.update(task, description="Waiting in queue...")
                    elif state == 'PROCESSING':
                        progress.update(task, description="Processing videos...")
                    elif state == 'SUCCESS':
                        progress.stop()
                        console.print("[green]✓ Analysis complete![/green]\n")
                        return status_data.get('result')
                    elif state == 'FAILURE':
                        progress.stop()
                        error = status_data.get('error', 'Unknown error')
                        console.print(f"[red]✗ Analysis failed: {error}[/red]")
                        return None

                    time.sleep(poll_interval)

                except KeyboardInterrupt:
                    progress.stop()
                    console.print("\n[yellow]Analysis cancelled by user[/yellow]")
                    console.print(f"Task {task_id} is still running in background")
                    return None
                except Exception as e:
                    progress.stop()
                    console.print(f"[red]✗ Error polling status: {e}[/red]")
                    return None

    def display_results(self, results: Dict[str, Any]) -> None:
        """
        Display analysis results in formatted CLI output.

        Args:
            results: Analysis results dictionary
        """
        if not results:
            return

        # Summary statistics
        summary = results.get('summary', {})
        if summary:
            console.print(Panel.fit(
                f"[bold cyan]Analysis Summary[/bold cyan]\n\n"
                f"Total Videos: {summary.get('total_videos', 0):,}\n"
                f"Unique Channels: {summary.get('unique_channels', 0):,}\n"
                f"Date Range: {summary.get('date_range', {}).get('start', 'N/A')} to "
                f"{summary.get('date_range', {}).get('end', 'N/A')}\n"
                f"Total Watch Time: {summary.get('total_watch_time_hours', 0):.1f} hours",
                title="📊 Summary"
            ))

        # Top channels
        top_channels = results.get('top_channels', [])
        if top_channels:
            console.print(f"\n[bold cyan]Top 10 Channels[/bold cyan]")
            table = Table(show_header=True)
            table.add_column("Rank", style="cyan", width=6)
            table.add_column("Channel Name", style="white")
            table.add_column("Videos Watched", justify="right", style="yellow")

            for idx, channel in enumerate(top_channels[:10], 1):
                table.add_row(
                    f"#{idx}",
                    channel.get('channel_name', 'Unknown'),
                    str(channel.get('video_count', 0))
                )

            console.print(table)

        # Clusters
        clusters = results.get('clusters', [])
        if clusters:
            console.print(f"\n[bold cyan]Content Clusters[/bold cyan]")
            for idx, cluster in enumerate(clusters, 1):
                console.print(f"\n[yellow]Cluster {idx}:[/yellow] {cluster.get('label', 'Unknown')}")
                console.print(f"  Size: {cluster.get('size', 0)} videos")
                if keywords := cluster.get('keywords', []):
                    console.print(f"  Keywords: {', '.join(keywords[:5])}")

        # Export options
        console.print(f"\n[dim]Full results available in JSON format[/dim]")

    def export_results(self, results: Dict[str, Any], output_path: str) -> bool:
        """
        Export results to JSON file.

        Args:
            results: Analysis results
            output_path: Output file path

        Returns:
            True if successful, False otherwise
        """
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            console.print(f"[green]✓ Results exported to {output_path}[/green]")
            return True
        except Exception as e:
            console.print(f"[red]✗ Export failed: {e}[/red]")
            return False

    def interactive_mode(self) -> None:
        """Run interactive CLI mode with menu."""
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]YouTube Audit Engine - CLI Interface[/bold cyan]\n"
            "Analyze your YouTube watch history from the command line",
            title="🎬 Welcome"
        ))

        # Check backend health
        console.print("\n[cyan]Checking backend connection...[/cyan]")
        if not self.check_health():
            if not Confirm.ask("\n[yellow]Backend is not available. Continue anyway?[/yellow]"):
                return

        while True:
            console.print("\n[bold cyan]Main Menu[/bold cyan]")
            console.print("1. Analyze watch history file")
            console.print("2. Check backend status")
            console.print("3. Exit")

            choice = Prompt.ask("\nSelect an option", choices=["1", "2", "3"], default="1")

            if choice == "1":
                file_path = Prompt.ask(
                    "\n[cyan]Enter path to watch-history.json[/cyan]",
                    default="watch-history.json"
                )

                results = self.analyze_watch_history(file_path)

                if results:
                    self.display_results(results)

                    if Confirm.ask("\n[cyan]Export results to JSON?[/cyan]", default=True):
                        output_path = Prompt.ask(
                            "Output file path",
                            default="youtube_audit_results.json"
                        )
                        self.export_results(results, output_path)

            elif choice == "2":
                console.print()
                self.check_health()

            elif choice == "3":
                console.print("\n[cyan]Goodbye![/cyan]")
                break

            if not Confirm.ask("\n[dim]Return to main menu?[/dim]", default=True):
                break


def main():
    """Main entry point for CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        description='YouTube Audit Engine - CLI Interface',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        'file',
        nargs='?',
        help='Path to watch-history.json file'
    )

    parser.add_argument(
        '--api-url',
        default=os.getenv('API_URL', 'http://localhost:8000'),
        help='Backend API URL (default: http://localhost:8000)'
    )

    parser.add_argument(
        '--api-token',
        default=os.getenv('API_BEARER_TOKEN'),
        help='API bearer token for authentication'
    )

    parser.add_argument(
        '--api-key',
        default=os.getenv('GOOGLE_API_KEY'),
        help='Google API key for YouTube Data API'
    )

    parser.add_argument(
        '--output', '-o',
        help='Output file path for results (JSON)'
    )

    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Run in interactive mode'
    )

    parser.add_argument(
        '--check-health',
        action='store_true',
        help='Check backend health and exit'
    )

    args = parser.parse_args()

    cli = YouTubeAuditCLI(api_url=args.api_url, api_token=args.api_token)

    # Health check mode
    if args.check_health:
        sys.exit(0 if cli.check_health() else 1)

    # Interactive mode
    if args.interactive or not args.file:
        cli.interactive_mode()
        return

    # Direct analysis mode
    results = cli.analyze_watch_history(args.file, args.api_key)

    if results:
        cli.display_results(results)

        if args.output:
            cli.export_results(results, args.output)

        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
