# Connection support

## Model config in `__init__`

Just like example in [batch run](#batch-run-with-yaml), it's supported to reference connection in ModelConfig.
And connection will be resolved and flatten connection's fields to ModelConfig.

## Connection in `__init__`

It's also supported to directly pass connection by **name** in `__init__`. 

```python
class MyFlow:
    def __init__(self, my_connection: AzureOpenAIConnection):
        pass
```

Note:

- Union of connection types(`Union[OpenAIConnection, AzureOpenAIConnection]`) is not supported.

### Batch run with connection

User can pass connection name to connection field in `init`.

In local, the connection name will be replaced with local connection object in execution time.
In cloud, the connection name will be replaced with workspace's connection object in execution time.

```python
# local connection "my_connection"'s instance will be passed to `__init__`
pf.run(flow="./flow.flex.yaml", init={"connection": "my_connection"}, data="./data.jsonl")
# cloud connection "my_cloud_connection"'s instance will be passed to `__init__`
pfazure.run(flow="./flow.flex.yaml", init={"connection": "my_cloud_connection"}, data="./data.jsonl")
```

## Environment variable connections(EVC)

If flow YAML has `environment_variables` and it's value is a connection reference like this:

```yaml
environment_variables:
  AZURE_OPENAI_API_KEY: ${open_ai_connection.api_key}
  AZURE_OPENAI_ENDPOINT: ${open_ai_connection.api_base}
```

The environment variable's value will be resolved to actual value in runtime.
If the connection not exist (in local or cloud), connection not found error will be raised.

**Note**: User can override the `environment_variables` with existing environment variable keys in `flow.flex.yaml`:

```bash
pf run create --flow . --data ./data.jsonl --environment-variables AZURE_OPENAI_API_KEY='${new_connection.api_key}' AZURE_OPENAI_ENDPOINT='my_endpoint'
```

Overriding with environment variable names which not exist in `flow.flex.yaml` is not supported.
Which means if user added environment variables which does not exist in `flow.flex.yaml` in runtime, it's value won't be resolved.

For example,

```bash
pf run create --flow . --data ./data.jsonl --environment-variables NEW_API_KEY='${my_new_connection.api_key}'
```

The `NEW_API_KEY`'s value won't be resolved to connection's API key.
