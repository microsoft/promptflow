# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import re
from io import open
from typing import Any, Match, cast

import pkg_resources
from setuptools import find_packages, setup

# Change the PACKAGE_NAME only to change folder and different name
PACKAGE_NAME = "promptflow-evals"
PACKAGE_PPRINT_NAME = "PromptFlow Evaluation SDK"

# a-b-c => a/b/c
PACKAGE_FOLDER_PATH = PACKAGE_NAME.replace("-", "/")
# a-b-c => a.b.c
NAMESPACE_NAME = PACKAGE_NAME.replace("-", ".")

# Version extraction inspired from 'requests'
with open(os.path.join(PACKAGE_FOLDER_PATH, "_version.py"), "r") as fd:
    version = cast(Match[Any], re.search(r'^VERSION\s*=\s*[\'"]([^\'"]*)[\'"]', fd.read(), re.MULTILINE)).group(1)
if not version:
    raise RuntimeError("Cannot find version information")

with open("README.md", encoding="utf-8") as f:
    readme = f.read()
with open("CHANGELOG.md", encoding="utf-8") as f:
    changelog = f.read()

setup(
    name=PACKAGE_NAME,
    version=version,
    description="Microsoft Azure {} Client Library for Python".format(PACKAGE_PPRINT_NAME),
    long_description_content_type="text/markdown",
    long_description=readme + "\n\n" + changelog,
    license="MIT License",
    author="Microsoft Corporation",
    author_email="azuresdkengsysadmins@microsoft.com",
    url="https://github.com/Azure/azure-sdk-for-python",
    keywords="azure, azuresdk, azure sdk",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
    ],
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(
        exclude=[
            "tests",
            "samples",
        ]
    ),
    python_requires="<4.0,>=3.8",
    install_requires=[
        # NOTE: To avoid breaking changes in a major version bump, all dependencies should pin an upper bound if possible.
        "azure-ai-ml>=1.14.0",
        "promptflow>=1.6.0",
        "promptflow-tools>=1.3.0",
    ],
    project_urls={
        "Bug Reports": "https://github.com/Azure/azure-sdk-for-python/issues",
        "Source": "https://github.com/Azure/azure-sdk-for-python",
    }
)
