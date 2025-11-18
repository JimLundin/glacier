#!/usr/bin/env python3
"""
Master Test Runner for All Glacier Examples.

This script runs all example files and reports their status.
Useful for validating that all examples work correctly.
"""

import sys
import traceback
from typing import Callable


def run_example_file(name: str, run_func: Callable) -> tuple[bool, str]:
    """
    Run an example file and return success status.

    Args:
        name: Name of the example file
        run_func: Function that runs the example

    Returns:
        Tuple of (success, message)
    """
    try:
        print(f"\n{'=' * 70}")
        print(f"Running: {name}")
        print('=' * 70)

        run_func()

        return True, "✓ Success"
    except Exception as e:
        error_msg = f"✗ Failed: {type(e).__name__}: {str(e)}"
        if "--verbose" in sys.argv:
            error_msg += f"\n{traceback.format_exc()}"
        return False, error_msg


def main():
    """Run all example files."""
    print("=" * 70)
    print("GLACIER TEST EXAMPLES - MASTER TEST RUNNER")
    print("=" * 70)
    print()
    print("This will run all example files to validate functionality.")
    print()

    results = []

    # DAG Patterns
    def run_dag_patterns():
        import dag_patterns
        # Module runs tests on import
        return True

    results.append(
        ("dag_patterns.py", run_example_file("DAG Patterns", run_dag_patterns))
    )

    # Task Patterns
    def run_task_patterns():
        import task_patterns
        return True

    results.append(
        ("task_patterns.py", run_example_file("Task Patterns", run_task_patterns))
    )

    # Dataset Patterns
    def run_dataset_patterns():
        import dataset_patterns
        return True

    results.append(
        ("dataset_patterns.py", run_example_file("Dataset Patterns", run_dataset_patterns))
    )

    # Error Cases (expected to have some failures)
    def run_error_cases():
        import error_cases
        return True

    results.append(
        ("error_cases.py", run_example_file("Error Cases", run_error_cases))
    )

    # Environment Patterns
    def run_environment_patterns():
        import environment_patterns
        return True

    results.append(
        ("environment_patterns.py", run_example_file("Environment Patterns", run_environment_patterns))
    )

    # Stack Patterns
    def run_stack_patterns():
        import stack_patterns
        return True

    results.append(
        ("stack_patterns.py", run_example_file("Stack Patterns", run_stack_patterns))
    )

    # Integration Examples
    def run_integration():
        import integration_examples
        return True

    results.append(
        ("integration_examples.py", run_example_file("Integration Examples", run_integration))
    )

    # Edge Cases
    def run_edge_cases():
        import edge_cases
        return True

    results.append(
        ("edge_cases.py", run_example_file("Edge Cases", run_edge_cases))
    )

    # Print Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()

    total = len(results)
    passed = sum(1 for _, (success, _) in results if success)
    failed = total - passed

    for filename, (success, message) in results:
        status_icon = "✓" if success else "✗"
        print(f"{status_icon} {filename:30s} {message}")

    print()
    print("=" * 70)
    print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
    print("=" * 70)

    # Exit with error code if any failed
    if failed > 0:
        print()
        print("⚠ Some examples failed. Run with --verbose for details.")
        sys.exit(1)
    else:
        print()
        print("✓ All examples passed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
