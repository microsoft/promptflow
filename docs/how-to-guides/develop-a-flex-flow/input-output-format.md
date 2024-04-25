# Input output format

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

## Supported types

We'll only support the following types in flow. Flow inits/inputs/outputs without specification will lead to validation error.

Inputs: primitive types(int, float, bool, str), dict, TypedDict, list

Outputs: primitive types(int, float, bool, str), dict, TypedDict, data class, list

Init: primitive types(int, float, bool, str), connection, ModelConfiguration, TypedDict, list

If user has non-supported types in code/YAML, validation error will be raised.

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

Stream is supported in flow.
Reference this [sample](https://microsoft.github.io/promptflow/tutorials/stream-flex-flow.html) for details.