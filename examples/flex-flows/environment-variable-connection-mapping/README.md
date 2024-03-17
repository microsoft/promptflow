# How to use environment variable with value from connection in prompt flow
When developer write an LLM app from scratch, they may not use the prompt flow connection. Instead, It's common to use environment variables to set API keys in local. In this example, we provide a tutorial about how to set environment variable with the values from connection. We call this as EVC (environment variable with connection) mapping.

## Prerequisites

Install promptflow sdk and other dependencies in this folder:

## What you will learn
Upon completing this tutorial, you should be able to:

- Learn how to set environment variable in prompt flow.
- Learn how to leverage prompt flow to load the secret values in connection into environment variable.
- Know the scenarios support using this feature.

We assume you've tried some other flex flow samples before learning this one. You know how to do flow test and batch run with a flex flow.

## Invoke flex flow using python intepreter

When you build your LLM from scratch, the environment variable comes from your own source. You can use below ways to set environment variables 
- Setup environment variables via terminal
bash:
```bash
export AZURE_OPENAI_API_KEY="your_key_here"
export AZURE_OPENAI_ENDPOINT="your_endpoint"
```
powershell:
```ps
$env:AZURE_OPENAI_API_KEY = "your_key_here"
$env:AZURE_OPENAI_ENDPOINT = "your_endpoint"
```
command line:
```cmd
set AZURE_OPENAI_API_KEY="your_key_here"
set AZURE_OPENAI_ENDPOINT="your_endpoint"
```

- Setup environment variables via .env file

Ensure you have put your azure open ai endpoint key in [.env](../.env) file. You can create one refer to this [example file](../.env.example).

```bash
cat .env
```

- Test flow

```bash
# run flow directly
python ./flow.py
```

## EVC mapping format
EVC mapping is a section in yaml/CLI parameter, the format is like below. The section's name is environment_variables, it's a list of key-value pair. The key represent the environment variable name. The value can be a string value of the environment variable, or a conneciton'sfield wrap with ${}. 
*To avoid expose plain secret in anywhere, we strongly recommend you to always use the connection field as the value in EVC mapping, instead of put real keys into this section. *
```bash
environment_variables: 
  AZURE_OPENAI_API_KEY: ${some_connection.api_key} 
  AZURE_OPENAI_ENDPOINT: ${some_connection.api_base} 
  AZURE_OPENAI_DEPLOYMENT_NAME: some_value
```

### EVC mapping format

There're multiple ways to set EVC mapping. We list them in order. When user run a flex flow using prompt flow VSC/SDK/CLI, pf SDK will try to lookup the EVC mapping from below location from top to down. And pf SDK will be responsible for resolving the connection and set the value into corresponding environment variable. 

1. During run submition: User can set EVC mapping in run.yaml, when user submit batch run, the EVC mapping in run.yaml will take effect.
```bash
# create run
pf run create --flow . --data ./data.jsonl --stream --environment-variables AZURE_OPENAI_API_KEY='${aoai.api_key}' AZURE_OPENAI_ENDPOINT='${open_ai_connection.api_base}' --column-mapping question='${data.question}'
# create run using yaml file
pf run create --file run.yml --stream
```
2. In flow definition: User can set EVC mapping in flow.dag.yaml
```bash
# test with default input value in flow.dag.yaml
pf flow test --flow . --environment-variables OPENAI_API_KEY='${aoai.api_key}' AZURE_OPENAI_ENDPOINT='${aoai.api_base}'
```
3. In global setting: User can set the EVC mapping in glbal setting. When doing that, the global setting only store the mapping instead of resolve real value.
```bash
# test with default input value in flow.dag.yaml
pf config set --environment-variables OPENAI_API_KEY='${aoai.api_key}' AZURE_OPENAI_ENDPOINT='${aoai.api_base}'
```
## Run flex flow using pf CLI with EVC mapping
Below table shows a summary of how prompt flow support set Environment variable in each stage:

| Environment | Operation   | Set value directly | Set connection mapping(${}) |
|-------------|-------------|--------------------------------|----------------------------------|
| Local       | Flow test   | Support                      | Support                        |
| Local       | Flow run    | Support                      | Support                        |
| Local       | Flow serve  | Support                      | Not Support                    |
| Local       | Flow build  | Support                      | Not Support                    |
| Local       | Flow run    | Support      | Support                        |
| Local to Cloud       | Flow test   | Support      | Support                        |
| Cloud       | Flow run    | Support      | Support                        |
| Cloud       | Flow clone  | Support      | Support                        |
| Cloud       | Flow deploy(to MIR) | Support      | Support                    |
| Cloud       | Flow to Component  | Support      | Supported                        |

## local behaviors
- When user do flow test or batch run in local, user can set environment variables, pf SDK support set both value or EVC mapping.
- When user deploy a flow as an endpoint using "pf flow serve" or build the flow as a docker/executable app using "pf flow build", pf SDK won't do the EVC mapping resolve work, because it's common to pass environment variable values when doing the deployment, and we cannot gurantee pf SDK has ability to access connections.
- (TODO: what's the behavior of flow load for EVC? Support set environment variable value, but no EVC mapping resolve?)
## submit flow to cloud with EVC
When run a flow in cloud, we need to get secret keys via connection stored in workspace. In that case, you can set the EVC mapping with valid connection in workspace.

- Create run
```bash
# run with environment variable reference connection in azureml workspace
pfazure run create --flow . --data ./data.jsonl --environment-variables AZURE_OPENAI_API_KEY='${aoai.api_key}' AZURE_OPENAI_ENDPOINT='${aoai.api_base}' --column-mapping question='${data.question}' --stream
# run using yaml file
pfazure run create --file run.yml --stream
```
## cloud behavior
When user author/run a flow in AzureML workspace/AI Studio project, there're ways 
- During flow authoring: User can edit the raw flow.dag.yaml file to specify the EVC mapping
- During flow batch run submit: User can set EVC mapping in batch run wizard, if user set here, it will overwrite the one in flow.dag.yaml
- During flow deployment: User can set EVC mapping in the deployment wizard, if user set here, it will overwrite the one in flow.dag.yaml

