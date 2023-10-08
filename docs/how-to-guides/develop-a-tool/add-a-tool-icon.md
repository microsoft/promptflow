# Add a Tool Icon
A tool icon serves as a graphical representation of your tool in the user interface (UI). Follow this guidance to add a custom tool icon when developing your own tool package.  

Adding a custom tool icon is optional. If you do not provide one, the system uses a default icon.

## Prerequisites

- Create a tool package as described in [Create and Use Tool Package](create-and-use-tool-package.md).
- Prepare a custom tool icon image. The image should meet following requirements:
  - The image should be in `PNG`, `JPG`, `GIF` or `BMP` format.
  - 16x16 pixel image to avoid distortion from resizing.
  - Avoid complex images with much detail or contrast as they may not resize well.   
  You could see for [example](https://github.com/microsoft/promptflow/blob/main/examples/tools/tool-package-quickstart/my_tool_package/icons/custom-tool-icon.png).
- Install dependencies of generating icon data URI:

  ```
  pip install pillow
  ```
## Generate a tool icon data URI
Run below command under the root folder to generate a data URI for your custom tool icon. Make sure the output file has an `.html` extension, this makes it easier to check the image's data URI: 
```
python <path-to-scripts>\tool\convert_image_to_data_url.py --image-path <image_input_path> -o <html_output_path>
```     
For example:
```
python D:\proj\github\promptflow\scripts\tool\convert_image_to_data_url.py --image-path D:\proj\github\promptflow\examples\tools\tool-package-quickstart\my_tool_package\icons\custom-tool-icon.png -o output.html
```
The content of `output.html` looks like the following, and you can open it in a web browser to see the result.
```html
<html>
<body>
<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAACq0lEQVR4nKWTPWxTVxiGn3N/bF/fGyd2YxsQ5LdSmoqGgKJMEQNZYGBFkVhY2JGYmFG3ioWZpWukqqpaqaVKq6pFIAECAkSxMA6RHZP4Jnbs+O/6xvdjcCLKT6ee7ZwjvfrOc55XiYjwP5bx740IZDf3+PVZicdrVeK2yfzJJBem02iaQv1XQCCCCNz+Lce91R1mRvtYd5uEDIfl9SqpWIjZLxOIgPooRQtE0JQiU6xx91mJfNkjZoX47vIkM2Nx6l6Xmz9kWHywgVIQBB++WImI1Nv7fP/XOqah0fKFdH8YQwXcf1Vh6WWZTrfLaDLK4rVZrJD+wSQGwJrbQtc0rs4PAXDr5xy/PHW5NJsmGQuhNI0/XrisFmtMjwxwOLVCYXTaTdq+kHagXq0iAo4phE2dn564XD8/zLlTRwn8gK1dQaHQtfcgDDMcwQo1Wc43mEp16YpibdsjEKHdEX5/8YZEpIhjCckBi9a+ibfvETEsIobdY1Bp+Pz4cAvP67C522IsbeN1A0zd5r77LWF7hebe1xxJrzKRmON56W/OHDnHwskbaCIQt03OTsbJljxeuz4rxSYXp2JcmYszedQhrNscj/ehJIKuQpiaBegHEFVPoOHBKOPpKMXdNtlSmzt/bpC0XTb9LxgcmGDq2CT5mpC0hhiO1UhGe8ANBYgCQ1dcnR9iJGnxT6ZMrtLmbV1H78/QrD0nagQ82ljCP+HzqLBEsB8wP7bQ+8ZDpoauuHA6xfnpFA3Px4mY3M2cJbeTZjTxFQYm44lv0MRkPDH1aRcOtdaUwon0rgrbBdbd10S1AXJbWRxzkLXNLDEz1VP54wDtQLHuQUl36xUKpTzl6jYFN89OdYeCm6eyV3mv8mdKxuFxueHS8PawTJuW3yAacmh26jiRfhL2IO8AhSUo7nmFnjUAAAAASUVORK5CYII=" alt="My Image">
</body>
</html>
```

## Use the tool icon data URI in the tool YAML
In the auto-generated tool YAML file, customize the tool icon by adding the data URI:
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