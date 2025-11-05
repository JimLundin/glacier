from setuptools import setup, find_packages

setup(
    name="glacier-pipeline",
    version="0.1.0",
    description="Code-centric data pipeline library with infrastructure-from-code generation",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Glacier Team",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "polars>=0.19.0",
        "pydantic>=2.0.0",
        "click>=8.0.0",
        "pyyaml>=6.0",
    ],
    extras_require={
        "aws": ["boto3>=1.28.0"],
        "gcp": ["google-cloud-storage>=2.10.0"],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
            "ruff>=0.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "glacier=glacier.cli.main:cli",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
