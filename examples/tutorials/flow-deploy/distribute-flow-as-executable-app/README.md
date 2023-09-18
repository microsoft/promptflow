# Distribute flow as executable app
This example demos how to package flow as a executable app. 
We will use [web-classification](../../../flows/standard/web-classification/README.md) as example in this tutorial.

Please ensure that you have installed all the required dependencies. You can refer to the "Prerequisites" section in the README of the [web-classification](../../../flows/standard/web-classification/README.md#Prerequisites) for a comprehensive list of prerequisites and installation instructions.

## Build a flow as docker format

Note that all dependent connections must be created before building as docker.
```bash
# create connection if not created before
pf connection create --file ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base> --name open_ai_connection
```

Use the command below to build a flow as docker format app:

```bash
pf flow build --source ../../../flows/standard/web-classification --output target --format docker
```
## Package flow model
### Prepare an entry file
A Python entry file is included as the entry point for the bundled app. We offer a Python file named `app.py`` here, which enables you to serve a flow folder as an endpoint.

```python
import os
import json
import argparse

from promptflow._cli._pf._connection import create_connection
from promptflow._cli._pf._flow import serve_flow

def create_connections(directory_path) -> None:
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            file_path = os.path.join(root, file)
            create_connection(file_path)


def set_environment_variable(file_path) -> None:
    with open(file_path, "r") as file:
        json_data = json.load(file)
    environment_variables = list(json_data.keys())
    for environment_variable in environment_variables:
        # Check if the required environment variable is set
        if not os.environ.get(environment_variable):
            print(f"{environment_variable} is not set.")
            user_input = input(f"Please enter the value for {environment_variable}: ")
            # Set the environment variable
            os.environ[environment_variable] = user_input


if __name__ == "__main__":
    create_connections("./connections")
    set_environment_variable("./settings.json")
    # Execute 'pf flow serve' command
    # setup argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default="flow",
    )
    parser.add_argument(
        "--port",
        default="8080",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
    )
    parser.add_argument(  # noqa: E731
        "--static_folder", type=str, help=argparse.SUPPRESS
    )

    parser.add_argument(
        "--environment-variables",
        help="Environment variables to set by specifying a property path and value. Example: --environment-variable "
        "key1='${my_connection.api_key}' key2='value2'. The value reference to connection keys will be resolved "
        "to the actual value, and all environment variables specified will be set into os.environ.",
        nargs="+",
    )

    args = parser.parse_args()
    serve_flow(args)
```

### Prepare a spec file
The spec file tells PyInstaller how to process your script. It encodes the script names and most of the options you give to the pyinstaller command. The spec file is actually executable Python code. PyInstaller builds the app by executing the contents of the spec file.

To streamline this process, we offer a `app.spec`` spec file that bundles the application into a single folder. For additional information on spec files, you can refer to the [Using Spec Files](https://pyinstaller.org/en/stable/spec-files.html).

```spec
# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[("./connections", "connections"), ("./flow", "flow"), ("./settings.json", ".")],
    hiddenimports=["promptflow", "promptflow-tools", "bs4"],
    hookspath=["."],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='app',
)
```

### Package flow using Pyinstaller
PyInstaller reads a spec file or Python script written by you. It analyzes your code to discover every other module and library your script needs in order to execute. Then it collects copies of all those files, including the active Python interpreter, and puts them with your script in a single folder, or optionally in a single executable file. 

Once you've placed the spec file `app.spec` and Python entry script `app.py` in the `target` folder generated in the [Build a flow as docker format](#build-a-flow-as-docker-format), you can package the flow model by using the following command:
```shell
cd target
pyinstaller app.spec
```
It will create two folders named `build` and `dist` within your specified output directory, denoted as `target`. The `build` folder houses various log and working files, while the `dist` folder contains the `app` executable folder. Inside the `dist` folder, you will discover the bundled application intended for distribution to your users.


#### Connections
If the service involves connections, all related connections will be exported as yaml files and recreated in the executable package.
Secrets in connections won't be exported directly. Instead, we will export them as a reference to environment variables:
```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/OpenAIConnection.schema.json
type: open_ai
name: open_ai_connection
module: promptflow.connections
api_key: ${env:OPEN_AI_CONNECTION_API_KEY} # env reference
```
We will prompt you to set up the environment variables in the console to make the connections work.

### Test the endpoint
Finally, You can compress the `dist` folder and distribute the bundle to other people. They can decompress it and execute your program by double clicking the executable file, e.g. `app.exe` in Windows system or executing the binary file, e.g. `app` in Linux system. 

Then they can open another terminal to test the endpoint with the following command:
```shell
curl http://localhost:8080/score --data '{"url":"https://play.google.com/store/apps/details?id=com.twitter.android"}' -X POST  -H "Content-Type: application/json"
```
Also, the development server has a built-in web page they can use to test the flow by openning 'http://localhost:8080' in the browser. The expected result is as follows if the flow served successfully, and the process will keep alive until it be killed manually.

To your users, the app is self-contained. They do not need to install any particular version of Python or any modules. They do not need to have Python installed at all.

**Note**: The executable generated is not cross-platform. One platform (e.g. Windows) packaged executable can't run on others (Mac, Linux). 
