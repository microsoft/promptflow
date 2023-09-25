# Tool Structure
The tool's structural path will be utilized by UI to display the hierarchical structure of the tool. If you do not specify a tool structure, the UI will display the tool at the root level.
- The structure string is not case-sensitive and must only contain characters from "a-zA-Z0-9-_".
- A maximum of three layers is allowed.

## Specifying Tool Structure
In the auto-generated tool YAML file, you have the option to customize your tool's structure by directly adding the structure path to the YAML file:
```
my_tool_package.tools.my_tool_1.my_tool:
    name: My First Tool
    description: This is my first tool
    structure: test/my_first_tool
    module: my_tool_package.tools.my_tool_1
    function: my_tool
    type: python
    inputs:
    connection:
        type:
        - CustomConnection
    input_text:
        type:
        - string
```