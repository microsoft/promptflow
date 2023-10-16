# FilePath input tool showcase

A case that shows how to use tool with FilePath as input.

## Prerequisites

1. Install promptflow sdk and other dependencies:

```bash
pip install -r requirements.txt
```

2. Build and install my_tools_packages. Go to root folder of tools\tool-package-quickstart, build and install.
   
```bash
cd ..\..\..\tools\tool-package-quickstart
python setup.py sdist bdist_wheel
pip install dist\my_tools_package-0.0.1-py3-none-any.whl --force-reinstall
cd ..\..\flows\standard\filepath-input-tool-showcase
```

## Flow description

As shown in following picture, the tool `Tool_with_FilePath_Input` has a input input_file with type `file_path`, which enables users to either select an existing file or create a new one, then pass it to a tool, allowing the tool to access the file's content. Here the flow.dag.yaml selects a default `hello_method.py`.

![flow_description](flow_description.png)

## Run flow

- Test flow

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .

```