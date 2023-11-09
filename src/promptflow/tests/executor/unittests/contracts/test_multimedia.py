import pytest

from promptflow.contracts.multimedia import PFBytes, Image


@pytest.mark.e2etest
class TestMultimediaContract:
    def test_constructors(self):
        content = b"test"
        mime_type = "image/*"
        bs = [
            PFBytes(content, mime_type),
            Image(content, mime_type),
            PFBytes(content, mime_type=mime_type),
            Image(content, mime_type=mime_type),
            PFBytes(value=content, mime_type=mime_type),
            Image(value=content, mime_type=mime_type),
        ]
        for b in bs:
            assert b._mime_type == "image/*"
            assert b._hash == "a94a8fe5"
            assert b.to_base64() == "dGVzdA=="
            assert bytes(b) == content
