import argparse
import os
import re
from jinja2 import Environment, FileSystemLoader
from pathlib import Path


def make_pythonic_variable_name(input_string):
    variable_name = input_string.strip()
    variable_name = re.sub(r'\W|^(?=\d)', '_', variable_name)
    if not variable_name[0].isalpha() and variable_name[0] != '_':
        variable_name = f'_{variable_name}'

    return variable_name


def convert_tool_name_to_class_name(tool_name):
    return ''.join(word.title() for word in tool_name.split('_'))


def create_file(path):
    with open(path, 'w'):
        pass


def create_folder(path):
    os.makedirs(path, exist_ok=True)


def create_tool_project_structure(destination: str, package_name: str, tool_name: str,
                                  function_name: str, is_class_way=False, demo_case="hello_world"):
    if is_class_way:
        class_name = convert_tool_name_to_class_name(tool_name)

    # Load templates
    templates_abs_path = Path("scripts/tool/templates").resolve()
    file_loader = FileSystemLoader(templates_abs_path)
    env = Environment(loader=file_loader)

    # Create new directory
    if os.path.exists(destination):
        print("Destination already exists. Please choose another one.")
        return

    os.makedirs(destination, exist_ok=True)

    # Generate setup.py
    template = env.get_template('setup.py.j2')
    output = template.render(package_name=package_name, tool_name=tool_name)
    with open(os.path.join(destination, 'setup.py'), 'w') as f:
        f.write(output)

    # Generate MANIFEST.in
    template = env.get_template('MANIFEST.in.j2')
    output = template.render(package_name=package_name)
    with open(os.path.join(destination, 'MANIFEST.in'), 'w') as f:
        f.write(output)

    # Create tools folder and __init__.py, tool.py inside it
    tools_dir = os.path.join(destination, package_name, 'tools')
    create_folder(tools_dir)
    create_file(os.path.join(tools_dir, '__init__.py'))
    with open(os.path.join(tools_dir, '__init__.py'), 'w') as f:
        f.write('__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore\n')

    # Generate tool.py
    if is_class_way:
        template = env.get_template('tool2.py.j2')
        output = template.render(class_name=class_name, function_name=function_name)
    else:
        if demo_case == "file_path":
            template = env.get_template('file_path_tool.py.j2')
        else:
            template = env.get_template('tool.py.j2')
        output = template.render(function_name=function_name)
    with open(os.path.join(tools_dir, f'{tool_name}.py'), 'w') as f:
        f.write(output)

    # Generate utils.py
    template = env.get_template('utils.py.j2')
    output = template.render()
    with open(os.path.join(tools_dir, 'utils.py'), 'w') as f:
        f.write(output)

    create_file(os.path.join(destination, package_name, '__init__.py'))
    with open(os.path.join(destination, package_name, '__init__.py'), 'w') as f:
        f.write('__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore\n')

    # Create yamls folder and __init__.py inside it
    yamls_dir = os.path.join(destination, package_name, 'yamls')
    create_folder(yamls_dir)

    # Create tool yaml
    if is_class_way:
        template = env.get_template('tool2.yaml.j2')
        output = template.render(package_name=package_name, tool_name=tool_name, class_name=class_name,
                                 function_name=function_name)
    else:
        if demo_case == "file_path":
            template = env.get_template('file_path_tool.yaml.j2')
        else:
            template = env.get_template('tool.yaml.j2')
        output = template.render(package_name=package_name, tool_name=tool_name, function_name=function_name)
    with open(os.path.join(yamls_dir, f'{tool_name}.yaml'), 'w') as f:
        f.write(output)

    # Create test folder and __init__.py inside it
    tests_dir = os.path.join(destination, 'tests')
    create_folder(tests_dir)
    create_file(os.path.join(tests_dir, '__init__.py'))

    # Create test_tool.py
    if is_class_way:
        template = env.get_template('test_tool2.py.j2')
        output = template.render(package_name=package_name, tool_name=tool_name, class_name=class_name,
                                 function_name=function_name)
    else:
        template = env.get_template('test_tool.py.j2')
        output = template.render(package_name=package_name, tool_name=tool_name, function_name=function_name)
    with open(os.path.join(tests_dir, f'test_{tool_name}.py'), 'w') as f:
        f.write(output)

    print(f'Generated tool package template for {package_name} at {destination}')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="promptflow tool template generation arguments.")

    parser.add_argument("--package-name", "-p", type=str, help="your tool package's name", required=True)
    parser.add_argument("--destination", "-d", type=str,
                        help="target folder you want to place the generated template", required=True)
    parser.add_argument("--tool-name", "-t", type=str,
                        help="your tool's name, by default is hello_world_tool", required=False)
    parser.add_argument("--function-name", "-f", type=str,
                        help="your tool's function name, by default is your tool's name", required=False)
    parser.add_argument("--use-class", action='store_true', help="Specify whether to use a class implementation way.")
    parser.add_argument("--case", "-c", type=str, required=False, default="hello_world", choices=["hello_world", "file_path"])
    args = parser.parse_args()

    destination = args.destination

    package_name = make_pythonic_variable_name(args.package_name)
    package_name = package_name.lower()

    if args.tool_name:
        tool_name = make_pythonic_variable_name(args.tool_name)
    else:
        tool_name = 'hello_world_tool'
    tool_name = tool_name.lower()

    if args.function_name:
        function_name = make_pythonic_variable_name(args.function_name)
    else:
        function_name = tool_name
    function_name = function_name.lower()

    create_tool_project_structure(destination, package_name, tool_name, function_name, args.use_class, args.case)
