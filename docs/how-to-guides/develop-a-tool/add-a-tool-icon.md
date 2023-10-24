# Add a Tool Icon
A tool icon serves as a graphical representation of your tool in the user interface (UI). Follow this guidance to add a custom tool icon when developing your own tool package.

Adding a custom tool icon is optional. If you do not provide one, the system uses a default icon.

## Prerequisites

- Please ensure that your [Prompt flow for VS Code](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow) is updated to version 1.0.10 or a more recent version.
- Create a tool package as described in [Create and Use Tool Package](create-and-use-tool-package.md).
- Prepare custom icon image that meets these requirements:

  - Use PNG, JPG or BMP format.
  - 16x16 pixels to prevent distortion when resizing.
  - Avoid complex images with lots of detail or contrast, as they may not resize well. 

  See [this example](https://github.com/microsoft/promptflow/blob/main/examples/tools/tool-package-quickstart/my_tool_package/icons/custom-tool-icon.png) as a reference.

## Add tool icon with _icon_ parameter

### Initialize a package tool with icon
Run the command below to initialize a package tool with icon:
```bash
pf tool init --package <package-name> --tool <tool-name> --set icon=<icon-path>
```
PF CLI will copy the icon file to the folder `<package-name>/icon/<icon-file-name>` and generate a tool script in the package. The tool icon will be configured in the tool script, the code is as follows:
```python
from pathlib import Path

from promptflow import tool
from promptflow.connections import CustomConnection


@tool(
    name="tool_name",
    description="This is tool_name tool",
    icon=Path(__file__).parent.parent / "icon" / <your-icon-file-name>,
)
def tool_name(connection: CustomConnection, input_text: str) -> str:
    # Replace with your tool code.
    # Usually connection contains configs to connect to an API.
    # Use CustomConnection is a dict. You can use it like: connection.api_key, connection.api_base
    # Not all tools need a connection. You can remove it if you don't need it.
    return "Hello " + input_text
```

The folder structure of the generated tool package is as follows:
```
<package-name>
│   MANIFEST.in
│   README.md
│   setup.py
│
├───icon
│       <icon-file-name>
│
└───<package-name>
        <tool-name>.py
        utils.py
        __init__.py
```



### Add an icon to an existing package tool

You can follow these steps to add an icon to an existing package tool:
1. Copy the icon image to the package folder.
2. Configure the icon for the tool.

    In the tool script, add the `icon` parameter to the decorator method `@tool`, and the parameter value is the `icon path`. The code is as follows:
    ```python
    from promptflow import tool

    @tool(name="tool_name", icon=<icon-path>)
    def tool_func(input_text: str) -> str:
        # Tool logic
        pass
    ```
3. Update `MANIFEST.in` in the package folder.

    This file is used to determine which files to include in the distribution of the project. You need to add the icon path relative to the package folder to this file.
    ```
    include <relative-icon-path>
    ```


## Verify the tool icon in VS Code extension
Follow [steps](create-and-use-tool-package.md#use-your-tool-from-vscode-extension) to use your tool from VS Code extension. Your tool displays with the custom icon:  
![custom-tool-with-icon-in-extension](../../media/how-to-guides/develop-a-tool/custom-tool-with-icon-in-extension.png)

## FAQ
### Can I preview the tool icon image before adding it to a tool?
Yes, you could run below command under the root folder to generate a data URI for your custom tool icon. Make sure the output file has an `.html` extension.
```
python <path-to-scripts>\tool\convert_image_to_data_url.py --image-path <image_input_path> -o <html_output_path>
```
For example:
```
python D:\proj\github\promptflow\scripts\tool\convert_image_to_data_url.py --image-path D:\proj\github\promptflow\examples\tools\tool-package-quickstart\my_tool_package\icons\custom-tool-icon.png -o output.html
```
The content of `output.html` looks like the following, open it in a web browser to preview the icon.
```html
<html>
<body>
<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAACR0lEQVR4nKWS3UuTcRTHP79nm9ujM+fccqFGI5viRRpjJgkJ3hiCENVN/QMWdBHUVRdBNwX9ARHd2FVEWFLRjaS9XPmSC/EFTNOWc3Pi48y9PHNzz68L7UXTCvreHM65+PA953uElFLyHzLvHMwsJrnzfJqFeAan3cKV9mr8XseeAOXX5vqjSS53jdF+tIz1nIFAMDCzwpvJ5b87+LSYYHw+gcWkEAwluXnOR2Q1R+9YjJ7BKJG4zoXmqr0ddL3+QnV5EeUOK821LsJammcjEeZiafJScrd3bm8H6zkDd4mVztZKAK49/Mj8is4Z/35GPq9R5VJ5GYztDtB1HT1vovGQSiqVAqDugI3I6jpP3i9x9VQVfu8+1N/OvbWCqqqoBSa6h1fQNA1N0xiYTWJSBCZF8HgwSjQapbRQ2RUg5NYj3O6ZochmYkFL03S4mImIzjFvCf2xS5gtCRYXWvBUvKXjyEVeTN/DXuDgxsnuzSMK4HTAw1Q0hZba4NXEKp0tbpq9VkxCwTAETrsVwxBIBIYhMPI7YqyrtONQzSznJXrO4H5/GJ9LUGg0YFYydJxoYnwpj1s9SEN5KzZz4fYYAW6dr+VsowdFgamlPE/Hs8SzQZYzg0S+zjIc6iOWDDEc6uND+N12B9/VVu+mrd79o38wFCCdTeBSK6hxBii1eahxBlAtRbsDdmoiHGRNj1NZ7GM0NISvzM9oaIhiqwOO/wMgl4FsRpLf2KxGXpLNSLLInzH+CWBIA6RECIGUEiEUpDRACBSh8A3pXfGWdXfMgAAAAABJRU5ErkJggg==" alt="My Image">
</body>
</html>
```
