#!/usr/bin/env python3
from setuptools import find_packages, setup


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


setup(
    name="mindtask",
    version="1.1.2",
    author="MindTask Team",
    description="A small SQLite task manager with CLI, desktop UI, and JSON-RPC integrations",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(include=["src", "src.*"]),
    package_dir={"": "."},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "flake8>=3.9",
        ],
        "mcp": [
            "mcp>=1.0",
        ],
        "ui": [
            "PySide6>=6.5",
            "QtAwesome>=1.4",
        ],
    },
    entry_points={
        "console_scripts": [
            "mindtask=src.cli.cli:main",
            "mindtask-ui=src.ui.app:main",
        ],
    },
    include_package_data=True,
)
