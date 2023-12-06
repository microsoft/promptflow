PromptFlow support image input/output by defining a contract of image data.

# Data class
promptflow.contracts.multimedia.Image
Image class is a subclass of `bytes`, thus you can access the binary data by directly using the object. It has an extra attribute `source_url` to store the origin of the image, which would be useful if you want to pass the url instead of content to APIs like LLM.

# Serialization/Deserialization
Url
Base64
File Reference

# Batch Input data
Batch input data containing image can be of 2 formats:
1. The same jsonl format of regular batch input, except that some column may be seriliazed image data or composite data type (dict/list) containing images. The serialized images can only be Url or Base64.
2. A folder containing a jsonl file under root path, which contains serialized image in File Reference format. The reference file are stored in the folder and there relative path to the root path is used as path in the file reference.