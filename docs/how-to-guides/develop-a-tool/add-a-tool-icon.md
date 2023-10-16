# Add a Tool Icon
A tool icon serves as a graphical representation of your tool in the user interface (UI). Follow this guidance to add a custom tool icon when developing your own tool package.

Adding a custom tool icon is optional. If you do not provide one, the system uses a default icon.

## Prerequisites

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
Use the `icon` parameter when generating your tool package to add a custom tool icon:
```
python <path-to-scripts>\tool\generate_tool_package_template.py --destination <your-tool-project> --package-name <your-package-name> --tool-name <your-tool-name> --function-name <your-tool-function-name> --icon <your-tool-icon-path>
```
For example:
```
python D:\proj\github\promptflow\scripts\tool\generate_tool_package_template.py --destination hello-world-proj --package-name hello-world --tool-name hello_world_tool --function-name get_greeting_message --icon D:\proj\github\promptflow\examples\tools\tool-package-quickstart\my_tool_package\icons\custom-tool-icon.png
```

In the auto-generated tool YAML file, the custom tool icon data URI is added in the `icon` field:
```yaml
hello_world.tools.hello_world_tool.get_greeting_message
  function: get_greeting_message
  inputs:
    connection:
      type:
      - CustomConnection
    input_text:
      type:
      - string
  module: hello_world.tools.hello_world_tool
  name: Hello World Tool
  description: This is hello world tool
  type: python
  icon: data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAACq0lEQVR4nKWTPWxTVxiGn3N/bF/fGyd2YxsQ5LdSmoqGgKJMEQNZYGBFkVhY2JGYmFG3ioWZpWukqqpaqaVKq6pFIAECAkSxMA6RHZP4Jnbs+O/6xvdjcCLKT6ee7ZwjvfrOc55XiYjwP5bx740IZDf3+PVZicdrVeK2yfzJJBem02iaQv1XQCCCCNz+Lce91R1mRvtYd5uEDIfl9SqpWIjZLxOIgPooRQtE0JQiU6xx91mJfNkjZoX47vIkM2Nx6l6Xmz9kWHywgVIQBB++WImI1Nv7fP/XOqah0fKFdH8YQwXcf1Vh6WWZTrfLaDLK4rVZrJD+wSQGwJrbQtc0rs4PAXDr5xy/PHW5NJsmGQuhNI0/XrisFmtMjwxwOLVCYXTaTdq+kHagXq0iAo4phE2dn564XD8/zLlTRwn8gK1dQaHQtfcgDDMcwQo1Wc43mEp16YpibdsjEKHdEX5/8YZEpIhjCckBi9a+ibfvETEsIobdY1Bp+Pz4cAvP67C522IsbeN1A0zd5r77LWF7hebe1xxJrzKRmON56W/OHDnHwskbaCIQt03OTsbJljxeuz4rxSYXp2JcmYszedQhrNscj/ehJIKuQpiaBegHEFVPoOHBKOPpKMXdNtlSmzt/bpC0XTb9LxgcmGDq2CT5mpC0hhiO1UhGe8ANBYgCQ1dcnR9iJGnxT6ZMrtLmbV1H78/QrD0nagQ82ljCP+HzqLBEsB8wP7bQ+8ZDpoauuHA6xfnpFA3Px4mY3M2cJbeTZjTxFQYm44lv0MRkPDH1aRcOtdaUwon0rgrbBdbd10S1AXJbWRxzkLXNLDEz1VP54wDtQLHuQUl36xUKpTzl6jYFN89OdYeCm6eyV3mv8mdKxuFxueHS8PawTJuW3yAacmh26jiRfhL2IO8AhSUo7nmFnjUAAAAASUVORK5CYII=
```

## Verify the tool icon in VS Code extension
Follow [steps](create-and-use-tool-package.md#use-your-tool-from-vscode-extension) to use your tool from VS Code extension. Your tool displays with the custom icon:  
![custom-tool-with-icon-in-extension](../../media/contributing/custom-tool-with-icon-in-extension.png)

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
<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAACq0lEQVR4nKWTPWxTVxiGn3N/bF/fGyd2YxsQ5LdSmoqGgKJMEQNZYGBFkVhY2JGYmFG3ioWZpWukqqpaqaVKq6pFIAECAkSxMA6RHZP4Jnbs+O/6xvdjcCLKT6ee7ZwjvfrOc55XiYjwP5bx740IZDf3+PVZicdrVeK2yfzJJBem02iaQv1XQCCCCNz+Lce91R1mRvtYd5uEDIfl9SqpWIjZLxOIgPooRQtE0JQiU6xx91mJfNkjZoX47vIkM2Nx6l6Xmz9kWHywgVIQBB++WImI1Nv7fP/XOqah0fKFdH8YQwXcf1Vh6WWZTrfLaDLK4rVZrJD+wSQGwJrbQtc0rs4PAXDr5xy/PHW5NJsmGQuhNI0/XrisFmtMjwxwOLVCYXTaTdq+kHagXq0iAo4phE2dn564XD8/zLlTRwn8gK1dQaHQtfcgDDMcwQo1Wc43mEp16YpibdsjEKHdEX5/8YZEpIhjCckBi9a+ibfvETEsIobdY1Bp+Pz4cAvP67C522IsbeN1A0zd5r77LWF7hebe1xxJrzKRmON56W/OHDnHwskbaCIQt03OTsbJljxeuz4rxSYXp2JcmYszedQhrNscj/ehJIKuQpiaBegHEFVPoOHBKOPpKMXdNtlSmzt/bpC0XTb9LxgcmGDq2CT5mpC0hhiO1UhGe8ANBYgCQ1dcnR9iJGnxT6ZMrtLmbV1H78/QrD0nagQ82ljCP+HzqLBEsB8wP7bQ+8ZDpoauuHA6xfnpFA3Px4mY3M2cJbeTZjTxFQYm44lv0MRkPDH1aRcOtdaUwon0rgrbBdbd10S1AXJbWRxzkLXNLDEz1VP54wDtQLHuQUl36xUKpTzl6jYFN89OdYeCm6eyV3mv8mdKxuFxueHS8PawTJuW3yAacmh26jiRfhL2IO8AhSUo7nmFnjUAAAAASUVORK5CYII=" alt="My Image">
</body>
</html>
```

### Can I add a tool icon to an existing tool package?
Yes, you can refer to the [preview icon](add-a-tool-icon.md#can-i-preview-the-tool-icon-image-before-adding-it-to-a-tool) section to generate the data URI and manually add the data URI to the tool's YAML file.
