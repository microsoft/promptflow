import pytest

from promptflow.contracts.multimedia import Image, PFBytes


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
            assert b.to_base64(True) == "data:image/*;base64,dGVzdA=="
            assert b.to_base64(True, True) == {"data:image/*;base64": "dGVzdA=="}
            assert bytes(b) == content
            assert b.source_url is None
            if isinstance(b, Image):
                assert str(b) == "Image(a94a8fe5)"
                assert repr(b) == "Image(a94a8fe5)"
                assert b.serialize() == "Image(a94a8fe5)"
                assert b.serialize(lambda x: x.to_base64()) == "dGVzdA=="
