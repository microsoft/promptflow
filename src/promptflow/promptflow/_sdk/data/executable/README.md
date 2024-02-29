Exported entry file & its dependencies are located in the same folder. The structure is as below:
- flow: the folder contains all the flow files
- connections: the folder contains yaml files to create all related connections
- app.py: the entry file is included as the entry point for the bundled application.
- app.spec: the spec file tells PyInstaller how to process your script.
- main.py: it will start streamlit service and be called by the entry file.
- utils.py: streamlit visualization relevant functions.
- config.json: a json file to store the settings for main.py.
- settings.json: a json file to store the settings of the executable application.
- build: a folder contains various log and working files.
- dist: a folder contains the executable application.
- README.md: the readme file to describe how to use the exported files and scripts.

Note: Please add your flow dependencies in requirements.txt in the same flow folder before build executable. We will
use packages there as hidden import in the pyinstaller spec file. For example:
```text
promptflow
bs4
azure.core
```

Please refer to [official doc](https://microsoft.github.io/promptflow/how-to-guides/deploy-a-flow/index.html)
for more details about how to use the exported files and scripts.
