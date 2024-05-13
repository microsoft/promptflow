---
resources: examples/connections/azure_openai.yml, examples/flows/standard/web-classification
category: deployment
weight: 50
---

# Distribute flow as executable app
This example demos how to package flow as a executable app.
We will use [web-classification](../../../flows/standard/web-classification/README.md) as example in this tutorial.

Please ensure that you have installed all the required dependencies. You can refer to the "Prerequisites" section in the README of the [web-classification](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/web-classification/) for a comprehensive list of prerequisites and installation instructions. And we recommend you to add a `requirements.txt` to indicate all the required dependencies for each flow.

[Pyinstaller](https://pyinstaller.org/en/stable/installation.html) is a popular tool used for converting Python applications into standalone executables. It allows you to package your Python scripts into a single executable file, which can be run on a target machine without requiring the Python interpreter to be installed.
[Streamlit](https://docs.streamlit.io/library/get-started) is an open-source Python library used for creating web applications quickly and easily. It's designed for data scientists and engineers who want to turn data scripts into shareable web apps with minimal effort.
We use Pyinstaller to package the flow and Streamlit to create custom web apps. Prior to distributing the workflow, kindly ensure that you have installed them.
In this example, we use PyInstaller version 5.13.2 and Streamlit version 1.26.0 within a Python 3.10.8 environment.

## Build a flow as executable format
Note that all dependent connections must be created before building as executable.
```bash
# create connection if not created before
pf connection create --file ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base> --name open_ai_connection
```
Use the command below to build a flow as executable format app:
```shell
pf flow build --source ../../../flows/standard/web-classification --output target --format executable
```

## Executable format folder structure
Exported files & its dependencies are located in the same folder. The structure is as below:
- flow: the folder contains all the flow files.
- connections: the folder contains yaml files to create all related connections.
- app.py: the entry file is included as the entry point for the bundled application.
- app.spec: the spec file tells PyInstaller how to process your script.
- main.py: it will start Streamlit service and be called by the entry file.
- settings.json: a json file to store the settings of the executable application.
- build: a folder contains various log and working files.
- dist: a folder contains the executable application.
- README.md: Simple introduction of the files.

### A template script of the entry file
PyInstaller reads a spec file or Python script written by you. It analyzes your code to discover every other module and library your script needs in order to execute. Then it collects copies of all those files, including the active Python interpreter, and puts them with your script in a single folder, or optionally in a single executable file.

We provide a Python entry script named [app.py](https://github.com/microsoft/promptflow/blob/main/src/promptflow-devkit/promptflow/_sdk/data/executable/app.py) as the entry point for the bundled app, which enables you to serve a flow folder as an endpoint.



### A template script of the spec file
The spec file tells PyInstaller how to process your script. It encodes the script names and most of the options you give to the pyinstaller command. The spec file is actually executable Python code. PyInstaller builds the app by executing the contents of the spec file.

To streamline this process, we offer a [app.spec.jinja2](https://github.com/microsoft/promptflow/blob/main/src/promptflow-devkit/promptflow/_sdk/data/executable/app.spec.jinja2) spec template file that bundles the application into a single file. For additional information on spec files, you can refer to the [Using Spec Files](https://pyinstaller.org/en/stable/spec-files.html).
Please replace {{streamlit_runtime_interpreter_path}} with the path of streamlit runtime interpreter in your environment.


### The bundled application using Pyinstaller
Once you've build a flow as executable format following [Build a flow as executable format](#build-a-flow-as-executable-format).
It will create two folders named `build` and `dist` within your specified output directory, denoted as <your-output-dir>. The `build` folder houses various log and working files, while the `dist` folder contains the `app` executable application.

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

## Test the endpoint
Finally, You can distribute the bundled application `app` to other people. They can execute your program by double clicking the executable file, e.g. `app.exe` in Windows system or running the binary file, e.g. `app` in Linux system.

The development server has a built-in web page they can use to test the flow by opening 'http://localhost:8501' in the browser. The expected result is as follows: if the flow served successfully, the process will keep alive until it is killed manually.

To your users, the app is self-contained. They do not need to install any particular version of Python or any modules. They do not need to have Python installed at all.

**Note**: The executable generated is not cross-platform. One platform (e.g. Windows) packaged executable can't run on others (Mac, Linux).

## Known issues
1. Note that Python 3.10.0 contains a bug making it unsupportable by PyInstaller. PyInstaller will also not work with beta releases of Python 3.13.
