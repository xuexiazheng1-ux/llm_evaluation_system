from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="llm-eval-cli",
    version="0.1.0",
    author="LLM Evaluation Team",
    description="CLI tool for LLM Evaluation System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0.0",
        "requests>=2.28.0",
        "tabulate>=0.9.0",
        "pyyaml>=6.0",
        "tqdm>=4.64.0",
        "colorama>=0.4.6",
    ],
    entry_points={
        "console_scripts": [
            "llm-eval=llm_eval.main:cli",
        ],
    },
)
