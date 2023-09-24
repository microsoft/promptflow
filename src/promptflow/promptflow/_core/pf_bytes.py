import base64
import json


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
        file_name = f"{id(obj)}.{obj.mime_type.split('/')[-1]}"  # A simple unique file name based on object id
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
    "myImage": PFBytes("image/png", b"Some mock binary data...")  # using mock bytes data for simplicity
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
