# Tool Icon
The tool icon serves as a graphical representation of your tool in the user interface (UI). If you do not provide a custom tool icon, the system will use a default one.

## Generating a Tool Icon from a Custom Image
You can use the following command to generate a data URI for your custom tool icon:
```
python scripts\tool\convert_image_to_data_url.py --image-path <image_input_path> -o <html_output_path>
```    
For example:
```
python scripts\tool\convert_image_to_data_url.py --image-path "AzureContentSafetyIcon.png" -o "output.html"
```
- To execute this script, use `pip install pillow`.
- Supported image formats include `PNG`, `JPG`, and `SVG`.
- The extension of the output file **must be** `html`. This will generate an HTML file at the specified output file path. To view the result, open the file in a web browser.  
- The script also checks the size of your image, and if necessary, automatically resizes it to 16*16 pixels. To maintain the quality of your image, consider the following suggestions:  
   - If possible, provide an image that is 16*16 pixels to avoid distortion from resizing.  
   - Avoid using complex images with a lot of detail or contrast, as they may not resize well.

## Using the Tool Icon in the Tool YAML File
In the auto-generated tool YAML file, you can customize your tool's icon by adding the tool icon's data URI directly to the YAML file:
```
my_tool_package.tools.my_tool_1.my_tool:
    name: My First Tool
    description: This is my first tool
    icon: data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAADDklEQVR4nG1TTWicVRQ9933v+yYZax0a0hBDJ7EIjaUTjTO2KwlCCtaFriJ0oQUhmaVgQrIo5XMMUmNU1EVgxuLGHzCBoW50kQyhUG1DMtqknaS6sCYWaZr+pTOTmXnfe++6GG1V5qwu3HsO53LvodHZ2BoE1pjx3WT/5TP+fJ9MvXBOg0EgMP4GMyiZicv2obwp5w4NCqYXAXRjNBfLAqhPM0tmdpaW0i4AjOd7O98pJHrfvXCoDQB89gX+hdFcLCtg6bzvQzAYRKSJyCQSyeD0L7F+N+zMPxpxfqJI6Oz41cNPpChlT68diaeX4mEAIEM/UN0e0/L6ja7dIhjYvHWjRW1T8WJkZNCEt6NGOYH0yDVV+6OxNu949ApBLFRr5rPxZy/NyukrvkdEauf6bwk30jpx/8/fC0ozOfqRaLG4pYXx2NZgjeFeoxFxFKLWmjbHxVl/vk8SM9Mnm9jbZmtfh00l8YcRC01698TGes9+7Yn0rj2SyneDLWWD4+W7tB4OiWNK8cVPXy4sAiACgPdv8kBTBNPFeyiFWrDr1h28/l4rfTE8m3hONptoUDGXPzq68isaQALAjsGTWoMrDGEBsEKJmYnIWQTsIgD4PkQqBVu/BkSK6rX0mWV1Cx1KgRXDLd60GiRuExEDD6+WSj38iX/IACBLywipNjwDF6JsIEQgbntC3QeA8lfdhz0qRU3grDSduNZwBWGfhlXAufC2LuyrlSqsq19Odey5xOnW10KmvCCbxYzD+rz6fN/zAMDTcP4j0J1J6nQ7nTylr3844laa39pYfCw3m/v4nnx8ipTS1U1TlQ61sMabdcrBBwID0wOOSCYzwRCzu2G95TLom5IMPWUJcWOaHBFAkgVBk2BFpf/bn3l1xoixuZ7h9rfJHOzq+PnbbPaN5trWsdW+I/1C7RxXyrsWcp1QddteUAFNAAAKq9r3IXwfYmyuZ/hBmBrhzmRXZ+mDzt7i1P69jfqjuViWxuZiq0y4ag2+nzy6ciaTT8qheFoDBGoQ50wyH4zkYoPC4iUiHPgLhm17gdgF0NgAAAAASUVORK5CYII=
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