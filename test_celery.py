#!/usr/bin/env python3
"""
Test script for verifying Celery setup.

This script tests basic Celery functionality including:
- Task execution
- Async task handling
- Progress tracking
- Task chaining
- Group execution

Usage:
    python test_celery.py
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.tasks import add, multiply, sleep_task, health_check
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.panel import Panel

console = Console()


def test_health_check():
    """Test Celery health check."""
    console.print("\n[bold cyan]Test 1: Health Check[/bold cyan]")

    try:
        result = health_check.delay()
        console.print(f"Task ID: {result.id}")
        console.print(f"Status: {result.status}")

        # Wait for result
        health = result.get(timeout=10)

        console.print("[green]✓ Health check passed[/green]")
        console.print(f"  Broker: {health['broker']}")
        console.print(f"  Backend: {health['backend']}")
        console.print(f"  Timestamp: {health['timestamp']}")
        return True

    except Exception as e:
        console.print(f"[red]✗ Health check failed: {e}[/red]")
        return False


def test_simple_task():
    """Test simple add task."""
    console.print("\n[bold cyan]Test 2: Simple Task (add)[/bold cyan]")

    try:
        # Execute synchronously
        result_sync = add(5, 3)
        console.print(f"Sync result: 5 + 3 = {result_sync}")

        # Execute asynchronously
        result_async = add.delay(10, 20)
        console.print(f"Task ID: {result_async.id}")
        console.print(f"Status: {result_async.status}")

        # Wait for result
        final_result = result_async.get(timeout=10)
        console.print(f"Async result: 10 + 20 = {final_result}")

        if final_result == 30:
            console.print("[green]✓ Simple task test passed[/green]")
            return True
        else:
            console.print(f"[red]✗ Expected 30, got {final_result}[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ Simple task test failed: {e}[/red]")
        return False


def test_progress_tracking():
    """Test task with progress tracking."""
    console.print("\n[bold cyan]Test 3: Progress Tracking (sleep_task)[/bold cyan]")

    try:
        duration = 5
        result = sleep_task.delay(duration)

        console.print(f"Task ID: {result.id}")
        console.print("Tracking progress...")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Sleeping...", total=duration)

            while not result.ready():
                if result.state == 'PROGRESS':
                    info = result.info
                    current = info.get('current', 0)
                    total = info.get('total', duration)
                    status = info.get('status', 'Working...')

                    progress.update(task, completed=current, description=status)

                time.sleep(0.5)

        final_result = result.get()
        console.print(f"Result: {final_result}")
        console.print("[green]✓ Progress tracking test passed[/green]")
        return True

    except Exception as e:
        console.print(f"[red]✗ Progress tracking test failed: {e}[/red]")
        return False


def test_task_chaining():
    """Test task chaining."""
    console.print("\n[bold cyan]Test 4: Task Chaining[/bold cyan]")

    try:
        from celery import chain

        # Create chain: (2 + 2) * 3 + 8 = 20
        workflow = chain(
            add.s(2, 2),      # Returns 4
            multiply.s(3),    # Receives 4, returns 12
            add.s(8)          # Receives 12, returns 20
        )

        result = workflow.apply_async()
        console.print(f"Chain ID: {result.id}")

        final_result = result.get(timeout=30)
        console.print(f"Chain result: (2 + 2) * 3 + 8 = {final_result}")

        if final_result == 20:
            console.print("[green]✓ Task chaining test passed[/green]")
            return True
        else:
            console.print(f"[red]✗ Expected 20, got {final_result}[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ Task chaining test failed: {e}[/red]")
        return False


def test_group_execution():
    """Test parallel task execution."""
    console.print("\n[bold cyan]Test 5: Parallel Execution (group)[/bold cyan]")

    try:
        from celery import group

        # Execute tasks in parallel
        job = group([
            add.s(2, 2),
            multiply.s(4, 5),
            add.s(10, 15)
        ])

        result = job.apply_async()
        console.print(f"Group ID: {result.id}")

        results = result.get(timeout=30)
        console.print(f"Group results: {results}")

        expected = [4, 20, 25]
        if results == expected:
            console.print("[green]✓ Group execution test passed[/green]")
            return True
        else:
            console.print(f"[red]✗ Expected {expected}, got {results}[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ Group execution test failed: {e}[/red]")
        return False


def main():
    """Run all Celery tests."""
    console.clear()

    # Banner
    banner = """
[bold cyan]
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     Celery Test Suite - YouTube Audit Engine             ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
[/bold cyan]
"""
    console.print(banner)

    console.print("[yellow]Make sure Redis and Celery worker are running:[/yellow]")
    console.print("  docker-compose up redis celery_worker")
    console.print("  OR")
    console.print("  celery -A backend.celery_app worker --loglevel=info\n")

    # Run tests
    tests = [
        ("Health Check", test_health_check),
        ("Simple Task", test_simple_task),
        ("Progress Tracking", test_progress_tracking),
        ("Task Chaining", test_task_chaining),
        ("Group Execution", test_group_execution),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except KeyboardInterrupt:
            console.print("\n[yellow]Tests interrupted by user[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Unexpected error in {test_name}: {e}[/red]")
            results.append((test_name, False))

    # Summary
    console.print("\n" + "="*60)
    console.print("\n[bold cyan]Test Summary[/bold cyan]\n")

    summary_table = Table(show_header=True)
    summary_table.add_column("Test", style="cyan")
    summary_table.add_column("Result", style="white")

    passed_count = 0
    for test_name, passed in results:
        if passed:
            summary_table.add_row(test_name, "[green]✓ PASSED[/green]")
            passed_count += 1
        else:
            summary_table.add_row(test_name, "[red]✗ FAILED[/red]")

    console.print(summary_table)

    total_tests = len(results)
    console.print(f"\n[bold]Results: {passed_count}/{total_tests} tests passed[/bold]")

    if passed_count == total_tests:
        console.print("\n[green]✓ All tests passed! Celery is working correctly.[/green]")
        console.print("\n[cyan]Next steps:[/cyan]")
        console.print("  1. View Flower monitoring at http://localhost:5555")
        console.print("  2. Implement analysis tasks in backend/tasks/analysis.py")
        console.print("  3. Update API endpoints to use async tasks")
        return 0
    else:
        console.print("\n[red]✗ Some tests failed. Please check your setup.[/red]")
        console.print("\n[yellow]Troubleshooting:[/yellow]")
        console.print("  - Verify Redis is running: redis-cli ping")
        console.print("  - Check Celery worker logs")
        console.print("  - Verify CELERY_BROKER_URL in .env")
        return 1


if __name__ == '__main__':
    sys.exit(main())
