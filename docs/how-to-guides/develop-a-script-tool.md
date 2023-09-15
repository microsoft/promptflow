# Develop a script tool
Custom script tool is supported if you want to extend the functionality of the tool, for example, call a third-party API 
or do some complex data processing.

A custom script tool is defined by a python function, and can be referenced and used as a flow node.

## Define a tool
A tool function is a python function with specific signatures. The function must be defined in a python file, and 
decorated with `@tool` function decorator.

The snippet below shows the basic structure of a tool function. Promptflow will read the function and extract inputs
from function parameters and type annotations. 

```python
from promptflow import tool
from promptflow.connections import CustomConnection

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def my_python_tool(input1: str, my_conn: CustomConnection) -> str:
    my_conn_dict = dict(my_conn)
    # Do some function call with my_conn_dict...
    return 'hello ' + input1
```

### Input Types

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

### Output
The tool function returns the output of the tool. The output type depends on the return annotation of the tool function. 
A return annotation is a way of specifying the type of the value that a function returns. 
For example, `def add(x: int, y: int) -> int:` means that the function add takes two integers as input and returns an integer as output.

## Use a tool in a flow
See how to [use a tool in a flow](develop-a-flow/develop-standard-flow.md#add-tool-as-your-need)

## Next steps
- [Develop a standard flow](develop-a-flow/develop-standard-flow.md)
- [Create and use your own tool package](how-to-create-and-use-your-own-tool-package.md)