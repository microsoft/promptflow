# Add Category and Tags for Tool
Users sometimes need their tools to be easy to find. To achieve this, we've introduced the `category` and `tags`. The tool category helps to organize tools into specific category folders, while the tool tags enables users to search for tools with similar tags, regardless of their categories.  
Both category and tags are optional. If a tool isn't assigned a category, it will be displayed in the root folder. Similarly, if no tags are assigned, the tags field will remain empty.

## Prerequisites
- Please ensure that your [Prompt flow for VS Code](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow) is updated to version 1.1.0 or a more recent version.

## How to add category and tags for a tool
Here we use [an existing tool](https://github.com/microsoft/promptflow/tree/main/examples/tools/tool-package-quickstart/my_tool_package/yamls/tool_with_file_path_input.yaml) as an example. If you want to create your own tool, please refer to [create and use tool package](create-and-use-tool-package.md#create-custom-tool-package), and you can add the _category_ and _tags_ fields in the tool's YAML.
The YAML should appear as follows:
```yaml
my_tool_package.tools.tool_with_file_path_input.my_tool:
  function: my_tool
  inputs:
    input_file:
      type:
      - file_path
    input_text:
      type:
      - string
  module: my_tool_package.tools.tool_with_file_path_input
  name: Tool with FilePath Input
  description: This is a tool to demonstrate the usage of FilePath input
  type: python
  # Add a category and tags as shown below.
  category: test_tool
  tags:
    input: FilePath
    task: text-generation
```

## Tool with category and tags shown in VS Code extension
### Tool with category and tags shown in tools tree
Follow [steps](create-and-use-tool-package.md#use-your-tool-from-vscode-extension) to use your tool from VS Code extension. Your tool will display with category and tags:  
![category_and_tags_in_extension](../../media/how-to-guides/develop-a-tool/category_and_tags_in_extension.png)

### Tool with category and tags shown in tool list
You can see your tools with category and tags when clicking `More` in the visual editor:  
![category_and_tags_in_tool_list](../../media/how-to-guides/develop-a-tool/category_and_tags_in_tool_list.png)  
Additionally, you can filter tools by tags:  
![filter_tools_by_tag](../../media/how-to-guides/develop-a-tool/filter_tools_by_tag.png)