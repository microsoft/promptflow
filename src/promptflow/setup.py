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
    "promptflow-tracing>=1.0.0",  # tracing capabilities
    "promptflow-core",  # core capabilities
    "promptflow-devkit",  # devkit capabilities
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
        "azure": [
            "azure-core>=1.26.4,<2.0.0",
            "azure-storage-blob[aio]>=12.17.0,<13.0.0",  # add [aio] for async run download feature
            "azure-identity>=1.12.0,<2.0.0",
            "azure-ai-ml>=1.14.0,<2.0.0",
            "pyjwt>=2.4.0,<3.0.0",  # requirement of control plane SDK
            "azure-cosmos>=4.5.1,<5.0.0",  # used to upload trace to cloud
        ],
        "executable": ["promptflow-devkit[executable]"],
        "azureml-serving": [
            # AzureML connection dependencies
            "azure-identity>=1.12.0,<2.0.0",
            "azure-ai-ml>=1.14.0,<2.0.0",
            # MDC dependencies for monitoring
            "azureml-ai-monitoring>=0.1.0b3,<1.0.0",
        ],
        "executor-service": [
            "promptflow-core[executor-service]",  # used to build web executor server
        ],
    },
    packages=find_packages(),
    scripts=["pf", "pf.bat"],
    entry_points={
        "console_scripts": [
            "pfazure = promptflow.azure._cli.entry:main",
            "pfs = promptflow._sdk._service.entry:main",
        ],
    },
    include_package_data=True,
    project_urls={
        "Bug Reports": "https://github.com/microsoft/promptflow/issues",
        "Source": "https://github.com/microsoft/promptflow",
    },
)
