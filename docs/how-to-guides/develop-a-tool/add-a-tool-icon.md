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
- Install dependencies to generate icon data URI:

  ```
  pip install pillow
  ```

## Add tool icon with _icon_ parameter 
Run the command below in your tool project directory to automatically generate your tool YAML, use _-i_ or _--icon_ parameter to add a custom tool icon:
```
python <path-to-scripts>\tool\generate_package_tool_meta.py -m <tool_module> -o <tool_yaml_path> -i <tool-icon-path>
```
Here we use [an existing tool project](https://github.com/microsoft/promptflow/tree/main/examples/tools/tool-package-quickstart) as an example.
```
cd D:\proj\github\promptflow\examples\tools\tool-package-quickstart

python D:\proj\github\promptflow\scripts\tool\generate_package_tool_meta.py -m my_tool_package.tools.my_tool_1 -o my_tool_package\yamls\my_tool_1.yaml -i my_tool_package\icons\custom-tool-icon.png
```

In the auto-generated tool YAML file, the custom tool icon data URI is added in the `icon` field:
```yaml
my_tool_package.tools.my_tool_1.my_tool:
  function: my_tool
  icon: data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAACR0lEQVR4nKWS3UuTcRTHP79nm9ujM+fccqFGI5viRRpjJgkJ3hiCENVN/QMWdBHUVRdBNwX9ARHd2FVEWFLRjaS9XPmSC/EFTNOWc3Pi48y9PHNzz68L7UXTCvreHM65+PA953uElFLyHzLvHMwsJrnzfJqFeAan3cKV9mr8XseeAOXX5vqjSS53jdF+tIz1nIFAMDCzwpvJ5b87+LSYYHw+gcWkEAwluXnOR2Q1R+9YjJ7BKJG4zoXmqr0ddL3+QnV5EeUOK821LsJammcjEeZiafJScrd3bm8H6zkDd4mVztZKAK49/Mj8is4Z/35GPq9R5VJ5GYztDtB1HT1vovGQSiqVAqDugI3I6jpP3i9x9VQVfu8+1N/OvbWCqqqoBSa6h1fQNA1N0xiYTWJSBCZF8HgwSjQapbRQ2RUg5NYj3O6ZochmYkFL03S4mImIzjFvCf2xS5gtCRYXWvBUvKXjyEVeTN/DXuDgxsnuzSMK4HTAw1Q0hZba4NXEKp0tbpq9VkxCwTAETrsVwxBIBIYhMPI7YqyrtONQzSznJXrO4H5/GJ9LUGg0YFYydJxoYnwpj1s9SEN5KzZz4fYYAW6dr+VsowdFgamlPE/Hs8SzQZYzg0S+zjIc6iOWDDEc6uND+N12B9/VVu+mrd79o38wFCCdTeBSK6hxBii1eahxBlAtRbsDdmoiHGRNj1NZ7GM0NISvzM9oaIhiqwOO/wMgl4FsRpLf2KxGXpLNSLLInzH+CWBIA6RECIGUEiEUpDRACBSh8A3pXfGWdXfMgAAAAABJRU5ErkJggg==
  inputs:
    connection:
      type:
      - CustomConnection
    input_text:
      type:
      - string
  module: my_tool_package.tools.my_tool_1
  name: my_tool
  type: python
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

### Can I add a tool icon to an existing tool package?
Yes, you can refer to the [preview icon](add-a-tool-icon.md#can-i-preview-the-tool-icon-image-before-adding-it-to-a-tool) section to generate the data URI and manually add the data URI to the tool's YAML file.
