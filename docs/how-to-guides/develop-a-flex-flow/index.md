# Develop a flex flow

We provide guides on how to develop a flow by writing a flow yaml from scratch in this section.

Flex flow provides a new way to deploy your LLM app in prompt flow. 
Which has the following benifits:

- Quick start (playground experience). Users can quickly test with prompt + python code with UI visualize experience. For example, user don't necessarily have to create YAML to run flex flow. See [batch run without YAML](./function-based-flow.md#batch-run-without-yaml) for more information.
- More advanced orchestration compared to DAG flow. Users can write complex flow with Python built-in control operators (if-else, foreach) or other 3rd party / open-source library.
- Easy onboard from other platforms: other platforms like langchain and sematic kernel already have code first flow authoring experience. We can onboard those customers with a few code changes.

## Supported types

We'll only support the following types in flex flow. Flow inits/inputs/outputs without specification will lead to validation error.

Inputs: primitive types(int, float, bool, str), dict, TypedDict, list

Outputs: primitive types(int, float, bool, str), dict, TypedDict, data class, list

Init: primitive types(int, float, bool, str), connection, ModelConfiguration, TypedDict, list

If user has non-supported types in code/YAML, validation error will be raised.

```python
# using unsupported types in flex flow will fail with validation error
class MyOwnClass:
  pass

class MyFlow:
    # not supported
    def __init__(self, my_own_obj: MyOwnClass):
```

```{toctree}
:maxdepth: 1

function-based-flow
class-based-flow
stream
```
