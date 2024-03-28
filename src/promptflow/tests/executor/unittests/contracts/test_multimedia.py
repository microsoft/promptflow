import pytest

from promptflow.contracts.multimedia import Image, PFBytes


@pytest.mark.unittest
class TestMultimediaContract:
    @pytest.mark.parametrize(
        "value, mime_type, source_url",
        [
            (b"test", "image/*", None),
            (b"test", "image/jpg", None),
            (b"test", "image/png", None),
            (b"test", None, None),
            (b"test", "image/*", "mock_url"),
        ],
    )
    def test_image_contract(self, value, mime_type, source_url):
        image = Image(value, mime_type, source_url)
        if mime_type is None:
            mime_type = "image/*"
        assert image._mime_type == mime_type
        assert image._hash == "a94a8fe5"
        assert image.to_base64() == "dGVzdA=="
        assert image.to_base64(with_type=True) == f"data:{mime_type};base64,dGVzdA=="
        assert bytes(image) == value
        assert image.source_url == source_url
        assert str(image) == "Image(a94a8fe5)"
        assert repr(image) == "Image(a94a8fe5)"
        assert image.serialize() == "Image(a94a8fe5)"
        assert image.serialize(lambda x: x.to_base64()) == "dGVzdA=="

    @pytest.mark.parametrize(
        "value, mime_type, source_url",
        [
            (b"test", "image/*", None),
            (b"test", "image/jpg", None),
            (b"test", "image/png", None),
            (b"test", "image/*", "mock_url"),
        ],
    )
    def test_pfbytes_contract(self, value, mime_type, source_url):
        pfBytes = PFBytes(value, mime_type, source_url)
        assert pfBytes._mime_type == mime_type
        assert pfBytes._hash == "a94a8fe5"
        assert pfBytes.to_base64() == "dGVzdA=="
        assert pfBytes.to_base64(with_type=True) == f"data:{mime_type};base64,dGVzdA=="
        assert bytes(pfBytes) == value
        assert pfBytes.source_url == source_url
