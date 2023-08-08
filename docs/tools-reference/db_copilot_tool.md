# DB Copilot

DB Copilot is a tool that can be used to generate sql query and get query results based on user input.

## Requirements
- curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
- curl https://packages.microsoft.com/config/ubuntu/20.04/prod.list > /etc/apt/sources.list.d/mssql-release.list
- apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql18=18.2.1.1-1
- apt-get install -y unixodbc-dev=2.3.11-1
- dbcopilot==0.3.3 --extra-index-url https://azuremlsdktestpypi.azureedge.net/dbcopilot
- db_copilot_tool==0.1.0 --extra-index-url https://azuremlsdktestpypi.azureedge.net/test-dbcopilottool



## Prerequisites
- Create db index from "Vector Index" tab of Prompt Flow

## Inputs

You can use the following parameters as inputs for this tool:

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| embedding_aoai_config | AzureOpenAIConnection | The connection to Azure Open AI for embedding. | Yes |
| chat_aoai_config | AzureOpenAIConnection | The connection to Azure Open AI for chat. | Yes |
| grounding_embedding_uri | string | The URI to the embedding data. Example: azureml://subscriptions/{subscription_id}/resourcegroups/{resource_group}/workspaces/{workspace_name}/datastores/{datastore_name}/paths/{relateive_path}. | Yes |
| example_embedding_uri | string | The URI to the example data. Example: azureml://subscriptions/{subscription_id}/resourcegroups/{resource_group}/workspaces/{workspace_name}/datastores/{datastore_name}/paths/{relateive_path}. | No |
| db_context_uri | string | The URI to the data base context. Example: azureml://subscriptions/{subscription_id}/resourcegroups/{resource_group}/workspaces/{workspace_name}/datastores/{datastore_name}/paths/{relateive_path}. | Yes |
| datastore_uri | string | The URI to the sql data store. Example: azureml://subscriptions/{subscription_id}/resourcegroups/{resource_group}/workspaces/{workspace_name}/datastores/{datastore_name}. | Yes |
| embedding_aoai_deployment_name | string | The azure open ai deployment name for embedding. | Yes |
| chat_aoai_deployment_name | string | The azure open ai deployment name for chat. | Yes |
| history_cache_enabled | bool | Whether enable history cache to track conversation. | No |
| history_cache_dir | string | The directory to store history cache. default: cache | No |
| query | string | The query you want to get | Yes |
| session_id | string | The session id to track chat history | No |

## Outputs

The following is an example JSON format response returned by the tool:

<details>
  <summary>Output</summary>
  
```json
[
  {
    "content": "```tsql\nSELECT COUNT(*) AS job_count FROM [jobs]\n```\n",
    "code_execute_result": {
      "source_id": null,
      "cost_ms": 13,
      "exception_message": null,
      "data": {
        "columns": [
          "job_count"
        ],
        "column_types": [
          "int"
        ],
        "data": [
          [
            19
          ]
        ],
        "caption": null
      }
    }
  }
]
```

</details>
