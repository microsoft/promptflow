import ast
import re
import subprocess
import copy
from pip._vendor import tomli as toml
from pathlib import Path
from promptflow._sdk._utilities.general_utils import render_jinja_template


def get_git_base_dir():
    return Path(
        subprocess.run(['git', 'rev-parse', '--show-toplevel'], stdout=subprocess.PIPE)
        .stdout.decode('utf-8').strip())


def is_tool(name):
    """Check whether `name` is on PATH and marked as executable."""

    # from whichcraft import which
    from shutil import which

    return which(name) is not None


def extract_requirements(file_path):
    with open(file_path, 'r') as file:
        tree = ast.parse(file.read())

    install_requires = []
    extras_requires = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and node.targets[0].id == 'REQUIRES':
            install_requires = [elt.s for elt in node.value.elts]
        elif isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'setup':
            for keyword in node.keywords:
                if keyword.arg == 'extras_require':
                    extras_requires = ast.literal_eval(keyword.value)
    return install_requires, extras_requires


def extract_package_names(packages):
    package_names = []
    for package in packages:
        match = re.match(r'^([a-zA-Z0-9-_.]+)', package)
        if match:
            package_names.append(match.group(1))
    return package_names


def get_toml_dependencies(packages):
    file_list = ["promptflow-tracing", "promptflow-core", "promptflow-devkit", "promptflow-azure"]
    dependencies = []

    for package in packages:
        if package in file_list:
            with open(get_git_base_dir() / "src" / package / "pyproject.toml", 'rb') as file:
                data = toml.load(file)
            extra_package_names = data.get('tool', {}).get('poetry', {}).get('dependencies', {})
            dependencies.extend(extra_package_names.keys())
    # hard-code promptflow-evals dependency here since it's not added in promptflow setup for now
    with open(get_git_base_dir() / "src" / "promptflow-evals" / "pyproject.toml", 'rb') as file:
        data = toml.load(file)
    extra_package_names = data.get('tool', {}).get('poetry', {}).get('dependencies', {})
    dependencies.extend(extra_package_names.keys())

    dependencies = [dependency for dependency in dependencies
                    if not dependency.startswith('promptflow') and not dependency == 'python']
    return dependencies


def get_package_dependencies(package_name_list):
    dependencies = []
    for package_name in package_name_list:
        if (is_tool('conda')):
            result = subprocess.run('conda activate root | pip show {}'.format(package_name),
                                    shell=True, stdout=subprocess.PIPE)
        else:
            result = subprocess.run(['pip', 'show', package_name], stdout=subprocess.PIPE)
        print("---" + package_name)
        print(result.stdout)
        lines = result.stdout.decode('utf-8', errors="ignore").splitlines()
        for line in lines:
            if line.startswith('Requires'):
                dependency = line.split(': ')[1].split(', ')
                if dependency != ['']:
                    dependencies.extend(dependency)
                break

    dependencies = [dependency for dependency in dependencies if not dependency.startswith('promptflow')]
    return dependencies


if __name__ == '__main__':
    dependencies = []
    install_requires, extras_requires = extract_requirements(get_git_base_dir() / 'src/promptflow/setup.py')
    install_requires_names = extract_package_names(install_requires)
    dependencies.extend(install_requires_names)

    for key in extras_requires:
        extras_require_names = extract_package_names(extras_requires[key])
        dependencies.extend(extras_require_names)
    # get toml dependencies
    dependencies = list(set(dependencies))
    direct_package_dependencies = get_toml_dependencies(dependencies)

    # get one step furture for dependencies
    dependencies = list(set(direct_package_dependencies))
    direct_package_dependencies = get_package_dependencies(dependencies)

    # get all dependencies
    all_packages = list(set(dependencies) | set(direct_package_dependencies))

    # remove all packages starting with promptflow
    all_packages = [package for package in all_packages if not package.startswith('promptflow')]

    hidden_imports = copy.deepcopy(all_packages)
    meta_packages = copy.deepcopy(all_packages)

    special_packages = ["streamlit-quill", "flask-cors", "flask-restx"]
    for i in range(len(hidden_imports)):
        # need special handeling because it use _ to import
        if hidden_imports[i] in special_packages:
            hidden_imports[i] = hidden_imports[i].replace('-', '_').lower()
        else:
            hidden_imports[i] = hidden_imports[i].replace('-', '.').lower()

    hidden_imports.remove("azure.storage.file.share")
    hidden_imports.append("azure.storage.fileshare")
    hidden_imports.remove("azure.storage.file.datalake")
    hidden_imports.append("azure.storage.filedatalake")

    render_context = {
        "hidden_imports": hidden_imports,
        "all_packages": all_packages,
        "meta_packages": meta_packages,
    }
    # always use unix line ending
    Path("./promptflow.spec").write_bytes(
        render_jinja_template(
            get_git_base_dir() / "scripts/installer/windows/scripts/promptflow.spec.jinja2", **render_context)
        .encode("utf-8")
        .replace(b"\r\n", b"\n"),)
