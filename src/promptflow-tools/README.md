### Test your tool locally
* Packages to install in order to run tool tests locally:
    ```cmd
    pip install promptflow-sdk[builtins] --extra-index-url https://azuremlsdktestpypi.azureedge.net/promptflow/
    ```
* Generate connections config.
  
  Firstly, add a connection block in [connections.json.example](connections.json.example) like this:
  ```json
  "translate_connection": {
      "type": "CustomConnection",
      "value": {
      "api_key": "translator-api-key",
      "api_endpoint": "https://api.cognitive.microsofttranslator.com/",
      "api_region": "global"
      },
      "module": "promptflow.connections"
  },
  ```
  Secondly, run below command to generate connections config:
  ```cmd
  python scripts\generate_connection_config.py --local
  ```
  Fill in the keys and secrets manually in `connections.json` when you run the tool test locally.
* Write tools tests under [tests folder](tests/). Please also add a test to ensure that tool output is json serializable. Run below command to test:
    ```cmd
    pytest src\promptflow-tools\tests\<your_tool_test>.py
    ```
* If your tool needs a connection with secrets in it, please use this [workflow](https://github.com/Azure/promptflow/actions/workflows/tool_secret_upload.yml) to upload secrets in key vault. The secrets you uploaded would be used in [Tool E2E CI](https://github.com/Azure/promptflow/actions/workflows/tool_tests.yml). Note that you only need to upload the SECRETS.
  > [!NOTE] After triggering the flow, kindly request approval from Promptflow Support before proceeding further.