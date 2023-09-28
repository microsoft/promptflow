# Add Tool Icon
The tool icon serves as a graphical representation of your tool in the user interface (UI). In this document, we will provide guidance on how to add a custom tool icon while developing your own tool package.  
Please note that this part is optional; if you do not provide a custom tool icon, the system will automatically use a default one. 

## Prerequisites
### Create the tool project
You can follow [Create and Use Tool Package](create-and-use-tool-package.md) to create your tool project.

### Install dependent library
Please install the dependent library by running the following command:
```
pip install pillow
```  
### Prepare your custom tool icon image
Supported image formats are `PNG` and `JPG`.  
The script in the following step will also verify the size of your image and, if necessary, automatically resize it to 16*16 pixels. To maintain the quality of your image, consider the following suggestions:
   - If possible, provide an image that is 16*16 pixels to avoid distortion from resizing.  
   - Avoid using complex images with a lot of detail or contrast, as they may not resize well.

## Generate tool icon data URI
You can generate a data URI for your custom tool icon by running the following command:
```
python <path-to-scripts>\tool\convert_image_to_data_url.py --image-path <image_input_path> -o <html_output_path>
```    
Ensure that the output file has the extension `.html`  
For example:
```
python D:\proj\github\promptflow\scripts\tool\convert_image_to_data_url.py --image-path D:\proj\github\promptflow\examples\tools\tool-package-quickstart\my_tool_package\icons\custom-tool-icon.png -o output.html
```
The contents of `output.html` should resemble the following:
```
<html>
<body>
<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAACq0lEQVR4nKWTPWxTVxiGn3N/bF/fGyd2YxsQ5LdSmoqGgKJMEQNZYGBFkVhY2JGYmFG3ioWZpWukqqpaqaVKq6pFIAECAkSxMA6RHZP4Jnbs+O/6xvdjcCLKT6ee7ZwjvfrOc55XiYjwP5bx740IZDf3+PVZicdrVeK2yfzJJBem02iaQv1XQCCCCNz+Lce91R1mRvtYd5uEDIfl9SqpWIjZLxOIgPooRQtE0JQiU6xx91mJfNkjZoX47vIkM2Nx6l6Xmz9kWHywgVIQBB++WImI1Nv7fP/XOqah0fKFdH8YQwXcf1Vh6WWZTrfLaDLK4rVZrJD+wSQGwJrbQtc0rs4PAXDr5xy/PHW5NJsmGQuhNI0/XrisFmtMjwxwOLVCYXTaTdq+kHagXq0iAo4phE2dn564XD8/zLlTRwn8gK1dQaHQtfcgDDMcwQo1Wc43mEp16YpibdsjEKHdEX5/8YZEpIhjCckBi9a+ibfvETEsIobdY1Bp+Pz4cAvP67C522IsbeN1A0zd5r77LWF7hebe1xxJrzKRmON56W/OHDnHwskbaCIQt03OTsbJljxeuz4rxSYXp2JcmYszedQhrNscj/ehJIKuQpiaBegHEFVPoOHBKOPpKMXdNtlSmzt/bpC0XTb9LxgcmGDq2CT5mpC0hhiO1UhGe8ANBYgCQ1dcnR9iJGnxT6ZMrtLmbV1H78/QrD0nagQ82ljCP+HzqLBEsB8wP7bQ+8ZDpoauuHA6xfnpFA3Px4mY3M2cJbeTZjTxFQYm44lv0MRkPDH1aRcOtdaUwon0rgrbBdbd10S1AXJbWRxzkLXNLDEz1VP54wDtQLHuQUl36xUKpTzl6jYFN89OdYeCm6eyV3mv8mdKxuFxueHS8PawTJuW3yAacmh26jiRfhL2IO8AhSUo7nmFnjUAAAAASUVORK5CYII=" alt="My Image">
</body>
</html>
```
To view the result, please open the file in a web browser. 

## Use the tool icon date URI in the tool YAML file
In the auto-generated tool YAML file, you can customize your tool's icon by adding the tool icon's data URI directly to the YAML file:
```
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

## Verify your tool icon in VSCode Extension
You can follow [Create and Use Tool Package](create-and-use-tool-package.md) to continue build the tool package and use it in VSCode Extension. After completing these steps, your tool will be displayed with your custom tool icon.
![custom-tool-with-icon.png](../../media/contributing/custom-tool-with-icon.png)