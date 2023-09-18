# Python

## Introduction
Users are empowered by the Python Tool to offer customized code snippets as self-contained executable nodes in PromptFlow.
Users can effortlessly create Python tools, edit code, and verify results with ease.

## Inputs

| Name   | Type   | Description                                          | Required |
|--------|--------|------------------------------------------------------|---------|
| Code   | string | Python code snippet                                  | Yes     |
| Inputs | -      | List of tool function parameters and its assignments | -       |


### Types

| Type | Python annotation             | Description                                |
| ---- |-------------------------------|--------------------------------------------|
| int | param: int                    | Integer type                               |
| bool | param: bool                   | Boolean type                               |
| string | param: str                    | String type                                |
| double | param: float                  | Double type                                |
| list | param: list or param: List[T] | List type                                  |
| object | param: dict or param: Dict[K, V] | Object type                                |
| xxConnection | param: xxConnection | Connection type, will be handled specially |


Parameters with `Connection` type annotation will be treated as connection inputs, promptflow will try to find
the connection name by the parameter value passed in during execution time.

Note that `Union[...]` type annotation is supported **ONLY** for connection type, 
for example, `param: Union[CustomConnection, OpenAIConnection]`.

## Outputs

The return of the python tool function. 


## How to write Python Tool?

### Guidelines

1. Python Tool Code should consist of a complete Python code, including any necessary module imports.

2. Python Tool Code must contain a function decorated with @tool (tool function), serving as the entry point for execution. The @tool decorator should be applied only once within the snippet.
   
   _Below sample defines python tool "my_python_tool", decorated with @tool_

3. Python tool function parameters must be assigned in 'Inputs' section

    _Below sample defines inputs "message" and assign with "world"_

4. Python tool function shall have return

    _Below sample returns a concatenated string_ 


### Code

The snippet below shows the basic structure of a tool function. Promptflow will read the function and extract inputs
from function parameters and type annotations. 

```python
from promptflow import tool
from promptflow.connections import CustomConnection

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def my_python_tool(message: str, my_conn: CustomConnection) -> str:
    my_conn_dict = dict(my_conn)
    # Do some function call with my_conn_dict...
    return 'hello ' + message
```

### Inputs

| Name    | Type   | Sample Value | 
|---------|--------|--------------|
| message | string | "world"      |
| my_conn | CustomConnection | "my_conn" |

Promptflow will try to find the connection named 'my_conn' during execution time.

### outputs

```python
"hello world"
```