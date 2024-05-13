# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import re
from pathlib import Path
from typing import Any, Match, cast

from setuptools import find_packages, setup

PACKAGE_NAME = "promptflow"
PACKAGE_FOLDER_PATH = Path(__file__).parent / "promptflow"

with open(os.path.join(PACKAGE_FOLDER_PATH, "_version.py"), encoding="utf-8") as f:
    version = cast(Match[Any], re.search(r'^VERSION\s*=\s*[\'"]([^\'"]*)[\'"]', f.read(), re.MULTILINE)).group(1)

with open("README.md", encoding="utf-8") as f:
    readme = f.read()
with open("CHANGELOG.md", encoding="utf-8") as f:
    changelog = f.read()

REQUIRES = [
    "promptflow-tracing==1.11.0.dev126475973",  # tracing capabilities
    "promptflow-core==1.11.0.dev126475973",  # core capabilities
    "promptflow-devkit==1.11.0.dev126475973",  # devkit capabilities
]

setup(
    name=PACKAGE_NAME,
    version=version,
    description="Prompt flow Python SDK - build high-quality LLM apps",
    long_description_content_type="text/markdown",
    long_description=readme + "\n\n" + changelog,
    license="MIT License",
    author="Microsoft Corporation",
    author_email="aml-pt-eng@microsoft.com",
    url="https://github.com/microsoft/promptflow",
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires="<4.0,>=3.8",
    install_requires=REQUIRES,
    extras_require={
        "all": [
            "promptflow-core[executor-service]==1.11.0.dev126475973",
            "promptflow-devkit[all]==1.11.0.dev126475973",
            "promptflow-azure==1.11.0.dev126475973",
            "promptflow-parallel==1.11.0.dev126475973",
        ],
        "azure": ["promptflow-azure==1.11.0.dev126475973"],
        "executable": ["promptflow-devkit[executable]==1.11.0.dev126475973"],
        "azureml-serving": [
            "promptflow-core[azureml-serving]==1.11.0.dev126475973",
        ],
        "executor-service": [
            "promptflow-core[executor-service]==1.11.0.dev126475973",  # used to build web executor server
        ],
    },
    scripts=["pf.autocomplete.sh"],
    packages=find_packages(),
    include_package_data=True,
    project_urls={
        "Bug Reports": "https://github.com/microsoft/promptflow/issues",
        "Source": "https://github.com/microsoft/promptflow",
    },
)
