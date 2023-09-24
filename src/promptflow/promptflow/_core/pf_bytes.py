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


def pfbytes_encoder(obj):
    """Dumps PFBytes to a file and returns its reference."""
    if isinstance(obj, PFBytes):
        file_name = f"{id(obj)}.{obj.mime_type.split('/')[-1]}"  # A simple unique file name based on object id
        obj.save_to_file(file_name)
        return {"pf_mime_type": obj.mime_type, "path": file_name}
    raise TypeError("Object of type '%s' is not JSON serializable" % type(obj).__name__)


def pfbytes_decoder(dct):
    """Loads PFBytes from a file."""
    if "pf_mime_type" in dct and "path" in dct:
        return PFBytes.load_from_file(dct["pf_mime_type"], dct["path"])
    return dct


# Sample usage
data = {
    "name": "John Doe",
    "audioClip": PFBytes("image/png", b"Some mock binary data...")  # using mock bytes data for simplicity
}

# Dump data to JSON string
json_str = json.dumps(data, default=pfbytes_encoder)
print(json_str)

# Load data back from JSON string
loaded_data = json.loads(json_str, object_hook=pfbytes_decoder)
print(loaded_data)
print(isinstance(loaded_data["audioClip"], PFBytes))  # This should print True
print(loaded_data["audioClip"].bytes)  # Should print the mock binary data