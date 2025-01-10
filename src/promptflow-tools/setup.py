import os
import re
from io import open
from typing import Any, List, Match, cast

from setuptools import find_namespace_packages, setup

PACKAGE_NAME = "promptflow-tools"
PACKAGE_FOLDER_PATH = "promptflow"


def parse_requirements(file_name: str) -> List[str]:
    with open(file_name) as f:
        return [
            require.strip() for require in f
            if require.strip() and not require.startswith('#')
        ]


# Version extraction inspired from 'requests'
with open(os.path.join(PACKAGE_FOLDER_PATH, "version.txt"), "r") as fd:
    version_content = fd.read()
    print(version_content)
    version = cast(Match[Any], re.search(r'^VERSION\s*=\s*[\'"]([^\'"]*)[\'"]', version_content, re.MULTILINE)).group(1)
if not version:
    raise RuntimeError("Cannot find version information")

with open("README.md", encoding="utf-8") as f:
    readme = f.read()

with open("CHANGELOG.md", encoding="utf-8") as f:
    changelog = f.read()

setup(
    name=PACKAGE_NAME,
    version=version,
    description="Prompt flow built-in tools",
    long_description_content_type="text/markdown",
    long_description=readme + "\n\n" + changelog,
    author="Microsoft Corporation",
    author_email="aml-pt-eng@microsoft.com",
    url="https://github.com/microsoft/promptflow",
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires="<4.0,>=3.9",
    install_requires=parse_requirements('requirements.txt'),
    extras_require={
        "azure": [
            # Dependency to list deployment in aoai_gpt4v
            "azure-mgmt-cognitiveservices==13.5.0"
        ]
    },
    packages=find_namespace_packages(include=[f"{PACKAGE_FOLDER_PATH}.*"]),
    entry_points={
        "package_tools": ["builtins = promptflow.tools.list:list_package_tools"],
    },
    include_package_data=True,
    project_urls={
        "Bug Reports": "https://github.com/microsoft/promptflow/issues",
        "Source": "https://github.com/microsoft/promptflow",
    },
)
