"""
Glacier Test Examples Package.

This package contains comprehensive examples for testing and documenting
the Glacier data pipeline framework.

Example usage:
    from glacier.test_examples.dag_patterns import example_linear_pipeline
    from glacier_local import LocalExecutor

    pipeline = example_linear_pipeline()
    results = LocalExecutor().execute(pipeline)
"""

__version__ = "0.1.0"
