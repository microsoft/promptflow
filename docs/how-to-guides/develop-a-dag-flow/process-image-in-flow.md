# Process image in flow

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

PromptFlow defines a contract to represent image data.

## Data class
`promptflow.contracts.multimedia.Image`
Image class is a subclass of `bytes`, thus you can access the binary data by directly using the object. It has an extra attribute `source_url` to store the origin url of the image, which would be useful if you want to pass the url instead of content of image to APIs like GPT-4V model.

## Data type in flow input
Set the type of flow input to `image` and promptflow will treat it as an image.

## Reference image in prompt template
In prompt templates that support image (e.g. in OpenAI GPT-4V tool), using markdown syntax to denote that a template input is an image: `![image]({{test_image}})`. In this case, `test_image` will be substituted with base64 or source_url (if set) before sending to LLM model.

## Serialization/Deserialization
Promptflow uses a special dict to represent image.
`{"data:image/<mime-type>;<representation>": "<value>"}`

- `<mime-type>` can be html standard [mime](https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Common_types) image types. Setting it to specific type can help previewing the image correctly, or it can be `*` for unknown type.
- `<representation>` is the image serialized representation, there are 3 supported types:

    - url

        It can point to a public accessable web url. E.g.

        {"data:image/png;url": "https://developer.microsoft.com/_devcom/images/logo-ms-social.png"}
    - base64

        It can be the base64 encoding of the image. E.g.

        {"data:image/png;base64": "iVBORw0KGgoAAAANSUhEUgAAAGQAAABLAQMAAAC81rD0AAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAABlBMVEUAAP7////DYP5JAAAAAWJLR0QB/wIt3gAAAAlwSFlzAAALEgAACxIB0t1+/AAAAAd0SU1FB+QIGBcKN7/nP/UAAAASSURBVDjLY2AYBaNgFIwCdAAABBoAAaNglfsAAAAZdEVYdGNvbW1lbnQAQ3JlYXRlZCB3aXRoIEdJTVDnr0DLAAAAJXRFWHRkYXRlOmNyZWF0ZQAyMDIwLTA4LTI0VDIzOjEwOjU1KzAzOjAwkHdeuQAAACV0RVh0ZGF0ZTptb2RpZnkAMjAyMC0wOC0yNFQyMzoxMDo1NSswMzowMOEq5gUAAAAASUVORK5CYII="}

    - path

        It can reference an image file on local disk. Both absolute path and relative path are supported, but in the cases where the serialized image representation is stored in a file, relative to the containing folder of that file is recommended, as in the case of flow IO data. E.g.

        {"data:image/png;path": "./my-image.png"}

Please note that `path` representation is not supported in Deployment scenario.

## Batch Input data
Batch input data containing image can be of 2 formats:
1. The same jsonl format of regular batch input, except that some column may be seriliazed image data or composite data type (dict/list) containing images. The serialized images can only be Url or Base64. E.g.
    ```json
    {"question": "How many colors are there in the image?", "input_image": {"data:image/png;url": "https://developer.microsoft.com/_devcom/images/logo-ms-social.png"}}
    {"question": "What's this image about?", "input_image": {"data:image/png;url": "https://developer.microsoft.com/_devcom/images/404.png"}}
    ```
2. A folder containing a jsonl file under root path, which contains serialized image in File Reference format. The referenced file are stored in the folder and their relative path to the root path is used as path in the file reference. Here is a sample batch input, note that the name of `input.jsonl` is arbitrary as long as it's a jsonl file:
    ```
    BatchInputFolder
    |----input.jsonl
    |----image1.png
    |----image2.png
    ```
    Content of `input.jsonl`
    ```json
    {"question": "How many colors are there in the image?", "input_image": {"data:image/png;path": "image1.png"}}
    {"question": "What's this image about?", "input_image": {"data:image/png;path": "image2.png"}}
    ```
