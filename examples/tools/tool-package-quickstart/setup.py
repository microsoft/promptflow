from setuptools import find_packages, setup

PACKAGE_NAME = "gega-tools-package"

setup(
    name=PACKAGE_NAME,
    version="2.0.2",
    description="This is my tools package",
    packages=find_packages(),
    entry_points={
        "package_tools": ["my_tools = my_tool_package.tools.utils:list_package_tools"],
    },
    include_package_data=True,   # This line tells setuptools to include files from MANIFEST.in
)
