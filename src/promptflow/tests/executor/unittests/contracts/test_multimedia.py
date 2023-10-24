import pytest
import base64
import hashlib
from promptflow.contracts.multimedia import PFBytes, Image


@pytest.mark.unittest
def test_PFBytes():
    test_bytes = b"test data"
    test_mime = "text/plain"
    pf = PFBytes(test_bytes, test_mime)

    assert isinstance(pf, PFBytes)
    assert pf._hash == hashlib.sha1(test_bytes).hexdigest()[:8]
    assert pf._mime_type == test_mime.lower()

    assert pf.to_base64() == "dGVzdCBkYXRh"
    assert pf.to_base64(with_type=True) == "data:text/plain;base64,dGVzdCBkYXRh"
    assert pf.to_base64() == base64.b64encode(test_bytes).decode("utf-8")
    assert pf.to_base64(with_type=True) == f"data:{test_mime};base64," + base64.b64encode(test_bytes).decode("utf-8")


@pytest.mark.unittest
def test_Image():
    test_bytes = b"image data"
    test_mime = "image/png"
    image = Image(test_bytes, test_mime)

    assert isinstance(image, Image)
    assert image._hash == hashlib.sha1(test_bytes).hexdigest()[:8]
    assert image._mime_type == test_mime.lower()
    assert str(image) == f"Image({image._hash})"
    assert repr(image) == f"Image({image._hash})"

    # Test serialize without encoder
    assert image.serialize() == f"Image({image._hash})"

    # Test serialize with encoder
    encoder = base64.b64encode
    assert image.serialize(encoder) == encoder(image)
