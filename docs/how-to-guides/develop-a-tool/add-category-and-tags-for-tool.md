# Adding Category and Tags for Tool

This document is dedicated to guiding you through the process of categorizing and tagging your tools for optimal organization and efficiency. Categories help you organize your tools into specific folders, making it much easier to find what you need. Tags, on the other hand, work like labels that offer more detailed descriptions. They enable you to quickly search and filter tools based on specific characteristics or functions. By using categories and tags, you'll not only tailor your tool library to your preferences but also save time by effortlessly finding the right tool for any task.

| Attribute | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| category  | str  | No       | Organizes tools into folders by common features. |
| tags      | dict | No       | Offers detailed, searchable descriptions of tools through key-value pairs. |

**Important Notes:**
- Tools without an assigned category will be listed in the root folder.
- Tools lacking tags will display an empty tags field.

## Prerequisites
- Please ensure that your [Prompt flow for VS Code](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow) is updated to version 1.1.0 or later.

## How to add category and tags for a tool

### Initialize a package tool with category and tags

You can use [pf tool init](../../reference/pf-command-reference.md#pf-tool-init) to initialize a package tool with category and tags:
```python
pf tool init --package <package-name> --tool <tool-name> --set category=<tool_category> tags=<tool_tags>
```

Here, we use an example to show the categories and tags of the tool after initialization. Assume that the user executes this command:
```python
pf tool init --package package_name --tool tool_name --set category="test_tool" tags="{'tag1':'value1','tag2':'value2'}"
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