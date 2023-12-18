import re
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from promptflow._utils.multimedia_utils import (
    _create_image_from_base64,
    _create_image_from_file,
    _create_image_from_url,
    _process_multimedia_dict_recursively,
    _process_recursively,
    convert_multimedia_data_to_base64,
    create_image,
    load_multimedia_data,
    persist_multimedia_data,
    resolve_multimedia_data_recursively,
)
from promptflow.contracts._errors import InvalidImageInput
from promptflow.contracts.flow import FlowInputDefinition
from promptflow.contracts.multimedia import Image
from promptflow.contracts.tool import ValueType

from ...utils import DATA_ROOT

TEST_IMAGE_PATH = DATA_ROOT / "logo.jpg"


@pytest.mark.unittest
class TestMultimediaUtils:
    @pytest.mark.parametrize("image_path", ["logo.jpg", "logo.png", "logo.webp", "logo.gif"])
    def test_create_image_from_base64(self, image_path):
        image = _create_image_from_file(DATA_ROOT / image_path)
        base64_str = image.to_base64()
        image_from_base64 = _create_image_from_base64(base64_str)
        assert str(image) == str(image_from_base64)
        format = image_path.split(".")[-1]
        mime_type = f"image/{format}" if format != "jpg" else "image/jpeg"
        assert mime_type == image_from_base64._mime_type

    @patch("requests.get")
    def test_create_image_from_url_with_mime_type(self, mock_get):
        url = "https://example.com/image.jpg"
        content = b"image content"
        mime_type = "image/jpeg"
        mock_get.return_value = MagicMock(status_code=200, content=content)

        image = _create_image_from_url(url, mime_type)

        assert isinstance(image, Image)
        assert image._mime_type == mime_type
        assert image.source_url == url

    @patch("requests.get")
    def test_create_image_from_url_failure(self, mock_get):
        url = "https://example.com/image.jpg"
        message = "Failed to fetch image"
        code = 404
        mock_get.return_value = MagicMock(status_code=code, text=message)

        with pytest.raises(InvalidImageInput) as ex:
            _create_image_from_url(url)

        expected_message = f"Failed to fetch image from URL: {url}. Error code: {code}. Error message: {message}."
        assert str(ex.value) == expected_message

    def test_create_image_with_dict(self, mocker):
        ## From path
        image_dict = {"data:image/jpg;path": TEST_IMAGE_PATH}
        image_from_path = create_image(image_dict)
        assert image_from_path._mime_type == "image/jpg"

        ## From base64
        image_dict = {"data:image/jpg;base64": image_from_path.to_base64()}
        image_from_base64 = create_image(image_dict)
        assert str(image_from_path) == str(image_from_base64)
        assert image_from_base64._mime_type == "image/jpg"

        ## From url
        mocker.patch("requests.get", return_value=mocker.Mock(content=image_from_path, status_code=200))
        image_dict = {"data:image/jpg;url": ""}
        image_from_url = create_image(image_dict)
        assert str(image_from_path) == str(image_from_url)
        assert image_from_url._mime_type == "image/jpg"

        mocker.patch("requests.get", return_value=mocker.Mock(content=None, status_code=404))
        with pytest.raises(InvalidImageInput) as ex:
            create_image(image_dict)
        assert "Failed to fetch image from URL" in ex.value.message_format

    def test_create_image_with_string(self, mocker):
        ## From path
        image_from_path = create_image(str(TEST_IMAGE_PATH))
        assert image_from_path._mime_type == "image/jpg"

        # From base64
        image_from_base64 = create_image(image_from_path.to_base64())
        assert str(image_from_path) == str(image_from_base64)
        assert image_from_base64._mime_type in ["image/jpg", "image/jpeg"]

        ## From url
        mocker.patch("promptflow._utils.multimedia_utils._is_url", return_value=True)
        mocker.patch("promptflow._utils.multimedia_utils._is_base64", return_value=False)
        mocker.patch("requests.get", return_value=mocker.Mock(content=image_from_path, status_code=200))
        image_from_url = create_image("")
        assert str(image_from_path) == str(image_from_url)
        assert image_from_url._mime_type in ["image/jpg", "image/jpeg"]

        ## From image
        image_from_image = create_image(image_from_path)
        assert str(image_from_path) == str(image_from_image)

    def test_create_image_with_invalid_cases(self):
        # Test invalid input type
        with pytest.raises(InvalidImageInput) as ex:
            create_image(0)
        assert "Unsupported image input type" in ex.value.message_format

        # Test invalid image dict
        with pytest.raises(InvalidImageInput) as ex:
            invalid_image_dict = {"invalid_image": "invalid_image"}
            create_image(invalid_image_dict)
        assert "Invalid image input format" in ex.value.message_format

    def test_persist_multimedia_date(self, mocker):
        image = _create_image_from_file(TEST_IMAGE_PATH)
        mocker.patch("builtins.open", mock_open())
        data = {"image": image, "images": [image, image, "other_data"], "other_data": "other_data"}
        persisted_data = persist_multimedia_data(data, base_dir=Path(__file__).parent)
        file_name = re.compile(r"^[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12}.jpg$")
        assert re.match(file_name, persisted_data["image"]["data:image/jpg;path"])
        assert re.match(file_name, persisted_data["images"][0]["data:image/jpg;path"])
        assert re.match(file_name, persisted_data["images"][1]["data:image/jpg;path"])

    def test_convert_multimedia_date_to_base64(self):
        image = _create_image_from_file(TEST_IMAGE_PATH)
        data = {"image": image, "images": [image, image, "other_data"], "other_data": "other_data"}
        base64_data = convert_multimedia_data_to_base64(data)
        assert base64_data == {
            "image": image.to_base64(),
            "images": [image.to_base64(), image.to_base64(), "other_data"],
            "other_data": "other_data",
        }

        base64_data = convert_multimedia_data_to_base64(data, with_type=True)
        prefix = f"data:{image._mime_type};base64,"
        assert base64_data == {
            "image": prefix + image.to_base64(),
            "images": [prefix + image.to_base64(), prefix + image.to_base64(), "other_data"],
            "other_data": "other_data",
        }

    def test_load_multimedia_data(self):
        # Case 1: Test normal node
        inputs = {
            "image": FlowInputDefinition(type=ValueType.IMAGE),
            "images": FlowInputDefinition(type=ValueType.LIST),
            "object": FlowInputDefinition(type=ValueType.OBJECT),
        }
        image_dict = {"data:image/jpg;path": str(TEST_IMAGE_PATH)}
        line_inputs = {
            "image": image_dict,
            "images": [image_dict, image_dict],
            "object": {"image": image_dict, "other_data": "other_data"},
        }
        updated_inputs = load_multimedia_data(inputs, line_inputs)
        image = _create_image_from_file(TEST_IMAGE_PATH)
        assert updated_inputs == {
            "image": image,
            "images": [image, image],
            "object": {"image": image, "other_data": "other_data"},
        }

        # Case 2: Test aggregation node
        line_inputs = {
            "image": [image_dict, image_dict],
            "images": [[image_dict, image_dict], [image_dict]],
            "object": [{"image": image_dict, "other_data": "other_data"}, {"other_data": "other_data"}],
        }
        updated_inputs = load_multimedia_data(inputs, line_inputs)
        assert updated_inputs == {
            "image": [image, image],
            "images": [[image, image], [image]],
            "object": [{"image": image, "other_data": "other_data"}, {"other_data": "other_data"}],
        }

    def test_resolve_multimedia_data_recursively(self):
        image_dict = {"data:image/jpg;path": "logo.jpg"}
        value = {
            "image": image_dict,
            "images": [image_dict, image_dict],
            "object": {"image": image_dict, "other_data": "other_data"},
        }
        input_dir = TEST_IMAGE_PATH
        updated_value = resolve_multimedia_data_recursively(input_dir, value)
        updated_image_dict = {"data:image/jpg;path": str(DATA_ROOT / "logo.jpg")}
        assert updated_value == {
            "image": updated_image_dict,
            "images": [updated_image_dict, updated_image_dict],
            "object": {"image": updated_image_dict, "other_data": "other_data"},
        }

    def test_process_recursively(self):
        image = _create_image_from_file(TEST_IMAGE_PATH)
        value = {"image": image, "images": [image, image], "object": {"image": image, "other_data": "other_data"}}
        process_funcs = {Image: lambda x: str(x)}
        updated_value = _process_recursively(value, process_funcs)
        image_str = str(image)
        assert updated_value == {
            "image": image_str,
            "images": [image_str, image_str],
            "object": {"image": image_str, "other_data": "other_data"},
        }
        assert value != updated_value

    def test_process_recursively_inplace(self):
        image = _create_image_from_file(TEST_IMAGE_PATH)
        value = {"image": image, "images": [image, image], "object": {"image": image, "other_data": "other_data"}}
        process_funcs = {Image: lambda x: str(x)}
        _process_recursively(value, process_funcs, inplace=True)
        image_str = str(image)
        assert value == {
            "image": image_str,
            "images": [image_str, image_str],
            "object": {"image": image_str, "other_data": "other_data"},
        }

    def test_process_multimedia_dict_recursively(self):
        def process_func(image_dict):
            return "image_placeholder"

        image_dict = {"data:image/jpg;path": "logo.jpg"}
        value = {
            "image": image_dict,
            "images": [image_dict, image_dict],
            "object": {"image": image_dict, "other_data": "other_data"},
        }
        updated_value = _process_multimedia_dict_recursively(value, process_func)
        assert updated_value == {
            "image": "image_placeholder",
            "images": ["image_placeholder", "image_placeholder"],
            "object": {"image": "image_placeholder", "other_data": "other_data"},
        }
