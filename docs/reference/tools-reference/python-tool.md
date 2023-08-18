# Python

## Introduction
Users are empowered by the Python Tool to offer customized code snippets as self-contained executable nodes in PromptFlow.
Users can effortlessly create Python tools, edit code, and verify results with ease.

## Inputs

| Name   | Type   | Description                                          | Required |
|--------|--------|------------------------------------------------------|---------|
| Code   | string | Python code snippet                                  | Yes     |
| Inputs | -      | List of tool function parameters and its assignments | -       |


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

```python
from promptflow import tool

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
@tool
def my_python_tool(message: str) -> str:
    return 'hello ' + message

```

### Inputs

| Name    | Type   | Sample Value | 
|---------|--------|--------------|
| message | string | "world"      |

### outputs

```python
"hello world"
```