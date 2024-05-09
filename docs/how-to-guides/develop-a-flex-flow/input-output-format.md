# Input output format

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

## Supported types

Promptflow officially support below types in flow.

- Inputs: primitive types(`int`, `float`, `bool`, `str`), `dict`, `TypedDict`, `list`

- Outputs: primitive types(`int`, `float`, `bool`, `str`), `dict`, `TypedDict`, `dataclass`, `list`

- Init: primitive types(`int`, `float`, `bool`, `str`), `Connection`(including custom connections), `ModelConfiguration`, `TypedDict`, `list`

If user has non-supported types in code/YAML, validation error will be raised.

### YAML support

Here's a mapping from python types to YAML types:

Python Type                     | YAML type                                                                        | Description
--------------------------------|----------------------------------------------------------------------------------|----------------------------------------------------
`int`                           | int                                                                              | Integer type
`float`                         | double                                                                           | Double type
`bool`                          | bool                                                                             | Boolean type
`str`                           | string                                                                           | String type
`list`                          | list                                                                             | List type
`dict`                          | object                                                                           | Dictionary type
`TypedDict`                     | object                                                                           | Typed dictionary type
`dataclass`                     | object                                                                           | Data class type
`CustomConnection`              | [Connection](../../concepts/concept-connections.md)                              | Connection type, will be handled specially
`OpenAIModelConfiguration`      | [OpenAIModelConfiguration](./model-config.md#openaimodelconfiguration)           | Model configuration type, will be handled specially
`AzureOpenAIModelConfiguration` | [AzureOpenAIModelConfiguration](./model-config.md#azureopenaimodelconfiguration) | Model configuration type, will be handled specially

Here's an sample YAML for above supported types.

```yaml
inputs:
  int_input:
    type: int
  float_input:
    type: double
  bool_input:
    type: bool
  string_input:
    type: string
  dict_input:
    type: object
  list_input:
    type: list
outputs:
  int_output:
    type: int
  float_output:
    type: double
  bool_output:
    type: bool
  string_output:
    type: string
  dict_output:
    type: object
  list_output:
    type: list
init:
  int_init:
    type: int
  float_init:
    type: double
  bool_init:
    type: bool
  string_init:
    type: string
  open_ai_connection:
    type: OpenAIConnection
  azure_open_ai_connection:
    type: AzureOpenAIConnection
  custom_connection:
    type: CustomConnection
  open_ai_model_config:
    type: OpenAIModelConfiguration
  azure_open_ai_model_config:
    type: AzureOpenAIModelConfiguration
```

### Unsupported type sample

```python
# using unsupported types in flow will fail with validation error
class MyOwnClass:
  pass

class MyFlow:
    # not supported
    def __init__(self, my_own_obj: MyOwnClass):
        pass

# not supported
def my_flow(my_own_obj: MyOwnClass):
    pass
```

Sample validation error: "The input 'my_own_obj' is of a complex python type. Please use a dict instead."

## Stream

Stream is supported in flow, you just need to return a generator type in your function.
Reference openai doc on how to do it using plain python code: [how_to_stream_completions](https://cookbook.openai.com/examples/how_to_stream_completions).

Reference this flow [sample](../../tutorials/chat-stream-with-flex-flow.ipynb) for details.
