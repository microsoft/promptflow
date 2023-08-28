import os
import re
from io import open
from typing import Any, Match, cast

from setuptools import find_namespace_packages, setup

PACKAGE_NAME = "promptflow-tools"
PACKAGE_FOLDER_PATH = "promptflow"

# Version extraction inspired from 'requests'
with open(os.path.join(PACKAGE_FOLDER_PATH, "version.txt"), "r") as fd:
    version_content = fd.read()
    print(version_content)
    version = cast(Match[Any], re.search(r'^VERSION\s*=\s*[\'"]([^\'"]*)[\'"]', version_content, re.MULTILINE)).group(1)
if not version:
    raise RuntimeError("Cannot find version information")

REQUIRES = [
    "google-search-results==2.4.1",
]

setup(
    name=PACKAGE_NAME,
    version=version,
    description="Builtin tools of prompt flow",
    author="Microsoft Corporation",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
    ],
    python_requires="<4.0,>=3.8",
    install_requires=REQUIRES,
    packages=find_namespace_packages(include=[f"{PACKAGE_FOLDER_PATH}.*"]),
    entry_points={
        "package_tools": ["builtins = promptflow.tools.list:list_package_tools"],
    },
    include_package_data=True,
)
