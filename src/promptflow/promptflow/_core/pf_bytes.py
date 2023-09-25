import base64
import json
import uuid

MIME_TYPE_FILE_EXTENSION_MAP = {
    "image/bmp": "bmp",
    "image/gif": "gif",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/svg+xml": "svg",
    "image/tiff": "tiff",
}


class PFBytes:
    def __init__(self, mime_type, bytes):
        self.mime_type = mime_type
        self.bytes = bytes

    def save_to_file(self, file_path):
        with open(file_path, 'wb') as file:
            file.write(self.bytes)

    @classmethod
    def load_from_file(cls, mime_type, file_path):
        with open(file_path, 'rb') as file:
            return cls(mime_type, file.read())

    def save_to_base64(self):
        return base64.b64encode(self.bytes).decode('utf-8')

    @classmethod
    def load_from_base64(cls, mime_type, base64_str):
        return cls(mime_type, base64.b64decode(base64_str))


def pfbytes_file_reference_encoder(obj):
    """Dumps PFBytes to a file and returns its reference."""
    if isinstance(obj, PFBytes):
        file_name = f"{uuid.uuid4()}"
        if obj.mime_type in MIME_TYPE_FILE_EXTENSION_MAP:
            file_name += f".{MIME_TYPE_FILE_EXTENSION_MAP[obj.mime_type]}"
        obj.save_to_file(file_name)
        return {"pf_mime_type": obj.mime_type, "path": file_name}
    raise TypeError("Object of type '%s' is not JSON serializable" % type(obj).__name__)


def pfbytes_file_reference_decoder(dct):
    """Loads PFBytes from a file."""
    if "pf_mime_type" in dct and "path" in dct:
        return PFBytes.load_from_file(dct["pf_mime_type"], dct["path"])
    return dct


def pfbytes_base64_encoder(obj):
    """Encodes PFBytes to base64."""
    if isinstance(obj, PFBytes):
        encoded_bytes = obj.save_to_base64()
        return {"pf_mime_type": obj.mime_type, "base64": encoded_bytes}
    raise TypeError("Object of type '%s' is not JSON serializable" % type(obj).__name__)


def pfbytes_base64_decoder(dct):
    """Decodes PFBytes from a base64 string."""
    if "pf_mime_type" in dct and "base64" in dct:
        decoded_bytes = PFBytes.load_from_base64(dct["pf_mime_type"], dct["base64"])
        return PFBytes(dct["pf_mime_type"], decoded_bytes)
    return dct


data = {
    "name": "John Doe",
    "myImage": PFBytes("image/png", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00d\x00\x00\x00K\x01\x03\x00\x00\x00\xbc\xd6\xb0\xf4\x00\x00\x00\x06PLTE\xfe\x00\x00\xff\xff\xff\x8aA\xe7\xb4\x00\x00\x00\x01bKGD\x00\x88\x05\x1dH\x00\x00\x00\tpHYs\x00\x00\x0b\x12\x00\x00\x0b\x12\x01\xd2\xdd~\xfc\x00\x00\x00\x07tIME\x07\xe5\x04\x1b\x10\x1c#\xa0\xf3\xd9\x90\x00\x00\x00\x12IDAT8\xcbc`\x18\x05\xa3`\x14\x8c\x02t\x00\x00\x04\x1a\x00\x01\xa3`\x95\xfb\x00\x00\x00\x00IEND\xaeB`\x82")  # using mock bytes data for simplicity
}

# Test file-based encode/decode
# Dump data to JSON string
json_str = json.dumps(data, default=pfbytes_file_reference_encoder)
print(json_str)

# Load data back from JSON string
loaded_data = json.loads(json_str, object_hook=pfbytes_file_reference_decoder)
print(loaded_data)
print(isinstance(loaded_data["myImage"], PFBytes))  # This should print True
print(loaded_data["myImage"].bytes)  # Should print the mock binary data

# Test base64 encode/decode
# Dump data to base64 encoded JSON string
json_base64_str = json.dumps(data, default=pfbytes_base64_encoder)
print(json_base64_str)

# Load data back from base64 encoded JSON string
loaded_data_base64 = json.loads(json_base64_str, object_hook=pfbytes_base64_decoder)
print(loaded_data_base64)
print(isinstance(loaded_data_base64["myImage"], PFBytes))  # This should print True
print(loaded_data_base64["myImage"].bytes)  # Should print the mock binary data
