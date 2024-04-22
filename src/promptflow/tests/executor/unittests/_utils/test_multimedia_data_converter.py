from unittest.mock import Mock

import pytest

from promptflow._utils.multimedia_data_converter import (
    AbstractMultimediaInfoConverter,
    BasicMultimediaFormatAdapter,
    MultimediaConverter,
    MultimediaInfo,
    OpenaiVisionMultimediaFormatAdapter,
    ResourceType,
)

from ...utils import DATA_ROOT, FLOW_ROOT

TEST_IMAGE_PATH = DATA_ROOT / "logo.jpg"


@pytest.mark.unittest
class TestMultimediaConverter:
    @pytest.mark.parametrize(
        "flow_file, converter_class",
        [
            (FLOW_ROOT / "chat_flow_with_openai_vision_image" / "flow.dag.yaml", OpenaiVisionMultimediaFormatAdapter),
            (FLOW_ROOT / "chat_flow_with_image" / "flow.dag.yaml", BasicMultimediaFormatAdapter),
            (FLOW_ROOT / "chat_flow_with_openai_vision_image" / "mock_chat.py", BasicMultimediaFormatAdapter),
            (None, BasicMultimediaFormatAdapter),
        ],
    )
    def test_create_converter(self, flow_file, converter_class):
        converter = MultimediaConverter(flow_file)
        assert isinstance(converter.format_adapter, converter_class)

    def test_convert_content_recursively(self):
        converter = MultimediaConverter(flow_file=None)

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
class TestBasicMultimediaFormatAdapter:
    def test_is_valid_format(self):
        adapter = BasicMultimediaFormatAdapter()
        assert adapter.is_valid_format({"data:image/jpg;path": "logo.jpg"})
        assert adapter.is_valid_format({"data:image/jpg;url": "https://example.com/logo.jpg"})
        assert not adapter.is_valid_format({"data:audio/mp3;path": "audio.mp3"})
        assert not adapter.is_valid_format({"data:video/mp4;url": "https://example.com/video.mp4"})

    def test_extract_info(self):
        adapter = BasicMultimediaFormatAdapter()

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
        adapter = BasicMultimediaFormatAdapter()
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


@pytest.mark.unittest
class TestOpenaiVisionMultimediaFormatAdapter:
    def test_is_valid_format(self):
        adapter = OpenaiVisionMultimediaFormatAdapter()
        assert adapter.is_valid_format({"type": "image_url", "image_url": {"url": "logo.jpg"}})
        assert not adapter.is_valid_format({"image_url": "data"})
        assert not adapter.is_valid_format(123)

    def test_extract_info(self):
        adapter = OpenaiVisionMultimediaFormatAdapter()

        # Valid formats
        expected_result = MultimediaInfo("image/*", ResourceType.PATH, "random_path")
        result = adapter.extract_info({"type": "image_file", "image_file": {"path": "random_path"}})
        assert result == expected_result

        expected_result = MultimediaInfo("image/*", ResourceType.URL, "https://example.com/logo.jpg")
        assert (
            adapter.extract_info({"type": "image_url", "image_url": {"url": "https://example.com/logo.jpg"}})
            == expected_result
        )

        expected_result = MultimediaInfo("image/*", ResourceType.BASE64, "data:image/jpeg;base64,/9j/12345ABC")
        assert (
            adapter.extract_info({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j/12345ABC"}})
            == expected_result
        )

        # Invalid format
        assert adapter.extract_info({"image_url": "data"}) is None
        assert adapter.extract_info({"type": "image_url", "image_url": {"erl": "ABCDE"}}) is None

    def test_create_data(self):
        adapter = OpenaiVisionMultimediaFormatAdapter()
        info = MultimediaInfo("image/jpeg", ResourceType.PATH, "random_path")
        expected_result = {"type": "image_file", "image_file": {"path": "random_path"}}
        assert adapter.create_data(info) == expected_result

        info = MultimediaInfo("image/jpeg", ResourceType.URL, "random_url")
        expected_result = {"type": "image_url", "image_url": {"url": "random_url"}}
        assert adapter.create_data(info) == expected_result

        info = MultimediaInfo("image/jpeg", ResourceType.BASE64, "base64 string")
        expected_result = {"type": "image_url", "image_url": {"url": "base64 string"}}
        assert adapter.create_data(info) == expected_result
