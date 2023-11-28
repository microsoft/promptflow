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
Run the command below in your tool project directory to automatically generate your tool YAML, use _-c_ or _--category_ to add category, and use _--tags_ to add tags for your tool:

```
python <promptflow github repo>\scripts\tool\generate_package_tool_meta.py -m <tool_module> -o <tool_yaml_path> --category <tool_category> --tags <tool_tags>
```

Here, we use [an existing tool](https://github.com/microsoft/promptflow/tree/main/examples/tools/tool-package-quickstart/my_tool_package/yamls/my_tool_1.yaml) as an example. If you wish to create your own tool, please refer to the [create and use tool package](create-and-use-tool-package.md#create-custom-tool-package) guide. 
```
cd D:\proj\github\promptflow\examples\tools\tool-package-quickstart

python D:\proj\github\promptflow\scripts\tool\generate_package_tool_meta.py -m my_tool_package.tools.my_tool_1 -o my_tool_package\yamls\my_tool_1.yaml --category "test_tool" --tags "{'tag1':'value1','tag2':'value2'}"
```
In the auto-generated tool YAML file, the category and tags are shown as below:
```yaml
my_tool_package.tools.my_tool_1.my_tool:
  function: my_tool
  inputs:
    connection:
      type:
      - CustomConnection
    input_text:
      type:
      - string
  module: my_tool_package.tools.my_tool_1
  name: My First Tool
  description: This is my first tool
  type: python
  # Category and tags are shown as below.
  category: test_tool
  tags:
    tag1: value1
    tag2: value2
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