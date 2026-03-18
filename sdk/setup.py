"""Ginie SDK — Package setup."""

from setuptools import setup, find_packages

setup(
    name="ginie-sdk",
    version="0.1.0",
    description="Python SDK for the Ginie AI-powered DAML contract generation platform",
    long_description=open("sdk/README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Ginie Team",
    url="https://github.com/ginie/ginie-sdk",
    license="MIT",
    packages=find_packages(include=["sdk", "sdk.*"]),
    python_requires=">=3.10",
    install_requires=[
        "httpx>=0.24.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="daml canton smart-contracts ai sdk",
)
