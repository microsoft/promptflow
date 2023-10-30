from setuptools import find_packages, setup

PACKAGE_NAME = "cli_tool_package"

setup(
    name=PACKAGE_NAME,
    version="0.0.1",
    description="This is my tools package",
    packages=find_packages(),
    entry_points={
        "package_tools": ["tool1 = cli_tool_package.utils:list_package_tools"],
    },
    install_requires=[
        "promptflow",
        "promptflow-tools"
    ]
)
