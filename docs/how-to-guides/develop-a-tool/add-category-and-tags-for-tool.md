# Add Category and Tags for Tool
Previously, all tools were listed at the top level. It would be challenging for users to find their desired tool, especially when dozens of tools are installed. To simplify the tool list and help users locate their target tools more easily, we've introduced `category` and `tags` features. The `category` feature helps organize tools into separate folders, while `tags` allow users to search and filter tools with matching tags.

| name     | type | is_required | description |
| ---------| -----| ---------- | ----------- |
| category | str  | false      | A string that groups tools with similar characteristics. |
| tags     | dict | false      | A dictionary of key-value pairs to describe the different perspectives of the tool. |
> [!Note] If a tool isn't assigned a category, it will be displayed in the root folder. Similarly, if no tags are assigned, the tags field will remain empty.

## Prerequisites
- Please ensure that your [Prompt flow for VS Code](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow) is updated to version 1.1.0 or later.

## How to add category and tags for a tool

### Initialize a package tool with category and tags

Run the command below to initialize a package tool with category and tags:
```python
pf tool init --package <package-name> --tool <tool-name> --set --category=<tool_category> --tags=<tool_tags>
```

Here, we use an example to show the categories and tags of the tool after initialization. Assume that the user executes this command:
```python
pf tool init --package package_name --tool tool_name --set --category="test_tool" --tags="{'tag1':'value1','tag2':'value2'}"
```
The generated tool script is as follows, where category and tags have been configured on the tool:
```python
from promptflow import tool
from promptflow.connections import CustomConnection


@tool(
    name="tool_name",
    description="This is tool_name tool",
    category='test_tool',
    tags={'tag1': 'value1', 'tag2': 'value2'},
)
def tool_name(connection: CustomConnection, input_text: str) -> str:
    # Replace with your tool code.
    # Usually connection contains configs to connect to an API.
    # Use CustomConnection is a dict. You can use it like: connection.api_key, connection.api_base
    # Not all tools need a connection. You can remove it if you don't need it.
    return "Hello " + input_text
```

### Configure category and tags on an existing package tool
Customer can configure category and tags directly on the tool script, as shown in the following code:
```python
@tool(
    name="tool_name",
    description="This is tool_name tool",
    category=<tool-category>,
    tags=<dict-of-the-tool-tags>,
)
def tool_name(input_text: str) -> str:
    # tool logic
    pass
```

## Tool with category and tags experience in VS Code extension
Follow the [steps](create-and-use-tool-package.md#use-your-tool-from-vscode-extension) to use your tool via the VS Code extension. 
- Experience in the tool tree  
![category_and_tags_in_tool_tree](../../media/how-to-guides/develop-a-tool/category_and_tags_in_tool_tree.png)  

- Experience in the tool list  
By clicking `More` in the visual editor, you can view your tools along with their category and tags:  
![category_and_tags_in_tool_list](../../media/how-to-guides/develop-a-tool/category_and_tags_in_tool_list.png)  
Furthermore, you have the option to search or filter tools based on tags:  
![filter_tools_by_tag](../../media/how-to-guides/develop-a-tool/filter_tools_by_tag.png)  