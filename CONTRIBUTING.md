# Contributing to Glacier

Thank you for your interest in contributing to Glacier! This document provides guidelines and information for contributors.

## Getting Started

### Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/glacier.git
   cd glacier
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**:
   ```bash
   pip install -e .
   pip install -r requirements.txt
   ```

4. **Run tests**:
   ```bash
   pytest tests/
   ```

### Project Structure

```
glacier/
├── glacier/               # Main package
│   ├── core/             # Core abstractions (Task, Pipeline, DAG)
│   ├── sources/          # Data source implementations
│   ├── sinks/            # Data sink implementations (future)
│   ├── runtime/          # Execution engines
│   ├── codegen/          # Code generation (Terraform, etc.)
│   └── cli/              # Command-line interface
├── examples/             # Example pipelines
├── tests/                # Test suite
└── docs/                 # Documentation
```

## How to Contribute

### Reporting Bugs

If you find a bug, please open an issue with:
- A clear, descriptive title
- Steps to reproduce the issue
- Expected behavior
- Actual behavior
- Your environment (OS, Python version, Glacier version)
- Minimal code example demonstrating the bug

### Suggesting Features

We welcome feature suggestions! Please open an issue with:
- A clear description of the feature
- Use cases and motivation
- Proposed API or interface (if applicable)
- Potential implementation approach (optional)

### Submitting Pull Requests

1. **Fork the repository** and create a branch:
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make your changes**:
   - Write clean, readable code
   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation as needed

3. **Run the test suite**:
   ```bash
   pytest tests/
   ```

4. **Run code formatters**:
   ```bash
   black glacier/ tests/ examples/
   ruff check glacier/ tests/ examples/
   ```

5. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Add feature: description of your changes"
   ```

6. **Push to your fork**:
   ```bash
   git push origin feature/my-new-feature
   ```

7. **Open a Pull Request** on GitHub

## Development Guidelines

### Code Style

- Follow PEP 8 style guidelines
- Use Black for code formatting
- Use Ruff for linting
- Use type hints where appropriate
- Write docstrings for public APIs

Example:

```python
def my_function(param: str) -> int:
    """
    Brief description of what the function does.

    Args:
        param: Description of the parameter

    Returns:
        Description of the return value

    Raises:
        ValueError: When and why this exception is raised
    """
    return len(param)
```

### Testing

- Write tests for all new functionality
- Aim for high test coverage (>80%)
- Use descriptive test names
- Test both success and failure cases
- Use fixtures for common test data

Example:

```python
class TestMyFeature:
    """Tests for my new feature."""

    def test_basic_functionality(self):
        """Test that basic case works correctly."""
        result = my_function("test")
        assert result == 4

    def test_error_handling(self):
        """Test that errors are handled properly."""
        with pytest.raises(ValueError):
            my_function(None)
```

### Documentation

- Update relevant documentation files
- Add docstrings to new classes and functions
- Include examples in docstrings
- Update DESIGN.md for architectural changes
- Add examples for new features

### Commit Messages

Write clear, descriptive commit messages:

```
Add S3 multipart upload support

- Implement multipart upload for large files
- Add retry logic for failed uploads
- Update S3Source to use multipart when needed
- Add tests for multipart upload

Fixes #123
```

Format:
- First line: Brief summary (50 chars or less)
- Blank line
- Detailed description with bullet points
- Reference related issues

## Areas for Contribution

### High Priority

1. **Additional Cloud Providers**
   - GCS (Google Cloud Storage) source
   - Azure Blob Storage source
   - Add generators for these providers

2. **Sinks**
   - Implement sink abstractions (write data)
   - S3Sink, LocalSink, etc.
   - Support different output formats

3. **Improved Analysis**
   - Better static analysis of pipeline code
   - Infer dependencies from data flow
   - Detect potential issues early

4. **Orchestration Integration**
   - Airflow DAG generation
   - Prefect flow generation
   - Dagster pipeline generation

5. **Testing & Examples**
   - More comprehensive tests
   - Real-world example pipelines
   - Performance benchmarks

### Medium Priority

1. **Data Quality**
   - Built-in data validation
   - Schema enforcement
   - Quality checks as tasks

2. **Monitoring & Observability**
   - Metrics collection
   - Logging integration
   - OpenTelemetry support

3. **Configuration Management**
   - Environment-based config
   - Secrets management
   - Parameter passing

4. **CLI Enhancements**
   - Interactive mode
   - Better error messages
   - Progress indicators

### Nice to Have

1. **Web UI**
   - DAG visualization
   - Pipeline monitoring
   - Configuration interface

2. **Streaming Support**
   - Streaming data sources
   - Continuous pipelines
   - Real-time processing

3. **Advanced Features**
   - Conditional execution
   - Dynamic task generation
   - Pipeline composition

## Architectural Principles

When contributing, please keep these principles in mind:

1. **Code-Centric**: Everything should be definable in Python
2. **Infrastructure from Code**: Generate infra from code, not the other way around
3. **Lazy by Default**: Leverage Polars' lazy evaluation
4. **Explicit over Implicit**: Users should be clear about what they're doing
5. **Extensibility**: Use adapters and plugins for customization
6. **Developer Experience**: Prioritize clean APIs and good error messages

## Review Process

All contributions go through code review:

1. **Automated Checks**: CI runs tests and linters
2. **Code Review**: Maintainers review code quality, design, tests
3. **Discussion**: Address feedback and iterate
4. **Approval**: Once approved, maintainers will merge

Please be patient - we'll try to review PRs within a few days, but it may take longer for complex changes.

## Community Guidelines

- Be respectful and professional
- Welcome newcomers and help them get started
- Provide constructive feedback
- Focus on the code, not the person
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md)

## Questions?

- Open a GitHub issue for bugs and features
- Join our Discord/Slack for discussions
- Check existing issues and PRs first
- Tag maintainers if you need help

## License

By contributing to Glacier, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Glacier! 🏔️
