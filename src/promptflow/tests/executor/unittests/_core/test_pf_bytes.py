import json
import pytest

from promptflow.contracts.pf_bytes import PFBytes, pfbytes_base64_encoder, pfbytes_base64_decoder


@pytest.mark.unittest
class TestToolLoader:
    def test_file_reference_encoder(self):
        data = {
            "name": "John Doe",
            "myImage": PFBytes("image/png", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00d\x00\x00\x00K\x01\x03\x00\x00\x00\xbc\xd6\xb0\xf4\x00\x00\x00\x06PLTE\xfe\x00\x00\xff\xff\xff\x8aA\xe7\xb4\x00\x00\x00\x01bKGD\x00\x88\x05\x1dH\x00\x00\x00\tpHYs\x00\x00\x0b\x12\x00\x00\x0b\x12\x01\xd2\xdd~\xfc\x00\x00\x00\x07tIME\x07\xe5\x04\x1b\x10\x1c#\xa0\xf3\xd9\x90\x00\x00\x00\x12IDAT8\xcbc`\x18\x05\xa3`\x14\x8c\x02t\x00\x00\x04\x1a\x00\x01\xa3`\x95\xfb\x00\x00\x00\x00IEND\xaeB`\x82")  # using mock bytes data for simplicity
        }

        # Test file-based encode/decode
        # Dump data to JSON string
        folder_path = "./temp"
        pfbytes_file_reference_encoder = PFBytes.get_file_reference_encoder(folder_path=folder_path)
        json_str = json.dumps(data, default=pfbytes_file_reference_encoder)

        # Load data back from JSON string
        pfbytes_file_reference_decoder = PFBytes.get_file_reference_decoder(folder_path=folder_path)
        loaded_data = json.loads(json_str, object_hook=pfbytes_file_reference_decoder)
        assert loaded_data['myImage'].mime_type == data["myImage"].mime_type
        assert loaded_data['myImage'].bytes == data["myImage"].bytes

    def test_base64_encode_decode(self):
        data = {
            "name": "John Doe",
            "myImage": PFBytes("image/png", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00d\x00\x00\x00K\x01\x03\x00\x00\x00\xbc\xd6\xb0\xf4\x00\x00\x00\x06PLTE\xfe\x00\x00\xff\xff\xff\x8aA\xe7\xb4\x00\x00\x00\x01bKGD\x00\x88\x05\x1dH\x00\x00\x00\tpHYs\x00\x00\x0b\x12\x00\x00\x0b\x12\x01\xd2\xdd~\xfc\x00\x00\x00\x07tIME\x07\xe5\x04\x1b\x10\x1c#\xa0\xf3\xd9\x90\x00\x00\x00\x12IDAT8\xcbc`\x18\x05\xa3`\x14\x8c\x02t\x00\x00\x04\x1a\x00\x01\xa3`\x95\xfb\x00\x00\x00\x00IEND\xaeB`\x82")  # using mock bytes data for simplicity
        }
        json_base64_str = json.dumps(data, default=pfbytes_base64_encoder)

        # Load data back from base64 encoded JSON string
        loaded_data = json.loads(json_base64_str, object_hook=pfbytes_base64_decoder)
        assert loaded_data['myImage'].mime_type == data["myImage"].mime_type
        assert loaded_data['myImage'].bytes == data["myImage"].bytes
