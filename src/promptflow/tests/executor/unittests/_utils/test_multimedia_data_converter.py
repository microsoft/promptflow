from pathlib import Path
from unittest.mock import Mock

import pytest

from promptflow._utils.multimedia_data_converter import (
    AbstractMultimediaInfoConverter,
    MultimediaConverter,
    MultimediaFormatAdapter20231201,
    MultimediaInfo,
    ResourceType,
)


@pytest.mark.unittest
class TestMultimediaConverter:
    def test_convert_content_recursively(self):
        converter = MultimediaConverter(Path("flow.yaml"))

        # Don't convert anything.
        content = {
            "image": {"data:image/jpg;url": "https://example.com/logo.jpg"},
            "images": [
                {"data:image/jpg;url": "https://example.com/logo.jpg"},
                {"data:image/jpg;base64": "base64 string"},
            ],
            "object": {"image": {"data:image/png;path": "random_path"}, "other_data": "other_data"},
        }
        mock_converter = Mock(spec=AbstractMultimediaInfoConverter)
        mock_converter.convert.side_effect = lambda x: x
        result = converter.convert_content_recursively(content, mock_converter)
        assert result == content

        # Convert all valid images.
        mock_converter.convert.side_effect = lambda x: MultimediaInfo("image/jpg", ResourceType("path"), "logo.jpg")
        result = converter.convert_content_recursively(content, mock_converter)
        expected_result = {
            "image": {"data:image/jpg;path": "logo.jpg"},
            "images": [
                {"data:image/jpg;path": "logo.jpg"},
                {"data:image/jpg;path": "logo.jpg"},
            ],
            "object": {"image": {"data:image/jpg;path": "logo.jpg"}, "other_data": "other_data"},
        }
        assert result == expected_result


@pytest.mark.unittest
class TestMultimediaFormatAdapter20231201:
    def test_is_valid_format(self):
        adapter = MultimediaFormatAdapter20231201()
        assert adapter.is_valid_format({"data:image/jpg;path": "logo.jpg"})
        assert adapter.is_valid_format({"data:image/jpg;url": "https://example.com/logo.jpg"})
        assert not adapter.is_valid_format({"data:audio/mp3;path": "audio.mp3"})
        assert not adapter.is_valid_format({"data:video/mp4;url": "https://example.com/video.mp4"})

    def test_extract_info(self):
        adapter = MultimediaFormatAdapter20231201()

        # Valid formats
        expected_result = MultimediaInfo("image/jpg", ResourceType.PATH, "random_path")
        assert adapter.extract_info({"data:image/jpg;path": "random_path"}) == expected_result

        expected_result = MultimediaInfo("image/jpg", ResourceType.URL, "random_url")
        assert adapter.extract_info({"data:image/jpg;url": "random_url"}) == expected_result

        expected_result = MultimediaInfo("image/jpg", ResourceType.BASE64, "random_base64")
        assert adapter.extract_info({"data:image/jpg;base64": "random_base64"}) == expected_result

        # Invalid format
        assert adapter.extract_info({"data:video/mp4;url": "https://example.com/video.mp4"}) is None
        assert adapter.extract_info({"data:image/mp4;url2": "https://example.com/video.mp4"}) is None
        assert adapter.extract_info({"content:image/mp4;path": "random_path"}) is None

    def test_create_data(self):
        adapter = MultimediaFormatAdapter20231201()
        info = MultimediaInfo("image/jpg", ResourceType.PATH, "random_path")
        expected_result = {"data:image/jpg;path": "random_path"}
        assert adapter.create_data(info) == expected_result

        info = MultimediaInfo("image/jpg", ResourceType.URL, "random_url")
        expected_result = {"data:image/jpg;url": "random_url"}
        assert adapter.create_data(info) == expected_result

        info = MultimediaInfo("image/jpg", ResourceType.BASE64, "base64 string")
        expected_result = {"data:image/jpg;base64": "base64 string"}
        assert adapter.create_data(info) == expected_result

        # Bad case when client provides invalid resource type.
        info = MultimediaInfo("image/jpg", "path", "base64 string")
        expected_result = {"data:image/jpg;base64": "base64 string"}
        with pytest.raises(AttributeError):
            adapter.create_data(info)
