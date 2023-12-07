PromptFlow defines a contract to represent image data.

# Data class
`promptflow.contracts.multimedia.Image`
Image class is a subclass of `bytes`, thus you can access the binary data by directly using the object. It has an extra attribute `source_url` to store the origin of the image, which would be useful if you want to pass the url instead of content to APIs like LLM.

# Serialization/Deserialization
Promptflow uses a special dict to preprent image.
`{"data:image/<mime-type>;<representation>": "<value>"}`
`<mime-type>` can be html standard image types which can help previewing correctly, or it can be `*` for unknown type.
`<representation>` is the image serilized representation, there are 3 supported types:

## url
It can point to a public accessable web url. E.g.
{"data:image/png;url": "https://developer.microsoft.com/_devcom/images/logo-ms-social.png"}

## base64
It can be the base64 encoding of the image. E.g.
{"data:image/png;base64": "<base64-string-of-the-image>"}

## path
It can reference an image file on local disk. Both absolute path and relative path are supported, but in the cases where the serlized image representation is stored in a file, relative path to the containing folder of that file is recommended, as in the case of flow IO data. E.g.
{"data:image/png;path": "./my-image.png"}

# Batch Input data
Batch input data containing image can be of 2 formats:
1. The same jsonl format of regular batch input, except that some column may be seriliazed image data or composite data type (dict/list) containing images. The serialized images can only be Url or Base64.
2. A folder containing a jsonl file under root path, which contains serialized image in File Reference format. The reference file are stored in the folder and there relative path to the root path is used as path in the file reference.
