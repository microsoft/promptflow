import pytest

from promptflow._utils.multimedia_format_converter import MultimediaConverter, MultimediaFormatConverter20231201


@pytest.mark.unittest
class TestMultimediaFormatConverter20231201:
    def test_is_image_dict(self):
        converter = MultimediaFormatConverter20231201()
        assert converter.is_multimedia_format({"data:image/jpg;path": "logo.jpg"})
        assert converter.is_multimedia_format({"data:image/jpg;url": "https://example.com/logo.jpg"})
        assert not converter.is_multimedia_format({"data:audio/mp3;path": "audio.mp3"})
        assert not converter.is_multimedia_format({"data:video/mp4;url": "https://example.com/video.mp4"})

    def test_extract_path(self):
        converter = MultimediaFormatConverter20231201()
        assert converter.get_path_from_multimedia_data({"data:image/jpg;path": "logo.jpg"}) == "logo.jpg"
        assert converter.get_path_from_multimedia_data({"data:image/png;path": "images/logo.png"}) == "images/logo.png"
        assert converter.get_path_from_multimedia_data({"data:image/webp;url": "https://example.com/logo.webp"}) is None
        assert converter.get_path_from_multimedia_data({"data:audio/mp3;path": "audio.mp3"}) is None

    def test_extract_url(self):
        converter = MultimediaFormatConverter20231201()
        assert (
            converter.get_url_from_multimedia_data({"data:image/jpg;url": "https://example.com/logo.jpg"})
            == "https://example.com/logo.jpg"
        )
        assert (
            converter.get_url_from_multimedia_data({"data:image/png;url": "https://example.com/images/logo.png"})
            == "https://example.com/images/logo.png"
        )
        assert converter.get_url_from_multimedia_data({"data:image/webp;path": "logo.webp"}) is None
        assert converter.get_url_from_multimedia_data({"data:audio/mp3;url": "https://example.com/audio.mp3"}) is None

    def test_generate_path(self):
        converter = MultimediaFormatConverter20231201()
        assert converter.create_multimedia_data_from_path({"data:image/jpg;path": "logo.jpg"}, "new_logo.jpg") == {
            "data:image/jpg;path": "new_logo.jpg"
        }
        assert converter.create_multimedia_data_from_path(
            {"data:image/png;url": "https://example.com/logo.png"}, "images/new_logo.png"
        ) == {"data:image/png;path": "images/new_logo.png"}
        assert converter.create_multimedia_data_from_path({"data:audio/mp3;path": "audio.mp3"}, "new_audio.mp3") is None

    def test_generate_url(self):
        converter = MultimediaFormatConverter20231201()
        assert converter.create_multimedia_data_from_url(
            {"data:image/jpg;url": "https://example.com/logo.jpg"}, "https://example.com/new_logo.jpg"
        ) == {"data:image/jpg;url": "https://example.com/new_logo.jpg"}
        assert converter.create_multimedia_data_from_url(
            {"data:image/png;path": "logo.png"}, "https://example.com/images/new_logo.png"
        ) == {"data:image/png;url": "https://example.com/images/new_logo.png"}
        assert (
            converter.create_multimedia_data_from_url(
                {"data:audio/mp3;url": "https://example.com/audio.mp3"}, "https://example.com/new_audio.mp3"
            )
            is None
        )


@pytest.mark.unittest
class TestMultimediaConverter:
    def test_convert_url_to_path_recursively(self):
        converter = MultimediaConverter(flow_file="path/to/yaml/file")

        value = {
            "image": {"data:image/jpg;url": "https://example.com/logo.jpg"},
            "images": [
                {"data:image/jpg;url": "https://example.com/logo.jpg"},
                {"data:image/jpg;url": "https://example.com/logo.jpg"},
            ],
            "object": {"image": {"data:image/jpg;path": "random_path"}, "other_data": "other_data"},
        }

        expected_value = {
            "image": {"data:image/jpg;path": "logo.jpg"},
            "images": [{"data:image/jpg;path": "logo.jpg"}, {"data:image/jpg;path": "logo.jpg"}],
            "object": {"image": {"data:image/jpg;path": "random_path"}, "other_data": "other_data"},
        }
        result = converter.convert_url_to_path_recursively(value, url_to_path_converter=lambda url: "logo.jpg")
        assert result == expected_value

    def test_convert_path_to_url_recursively(self):
        converter = MultimediaConverter(flow_file="path/to/yaml/file")
        value = {
            "image": {"data:image/jpg;path": "logo.jpg"},
            "images": [{"data:image/jpg;path": "logo.jpg"}, {"data:image/jpg;path": "logo.jpg"}],
            "object": {"image": {"data:image/jpg;url": "random_url"}, "other_data": "other_data"},
        }
        expected_value = {
            "image": {"data:image/jpg;url": "https://example.com/logo.jpg"},
            "images": [
                {"data:image/jpg;url": "https://example.com/logo.jpg"},
                {"data:image/jpg;url": "https://example.com/logo.jpg"},
            ],
            "object": {"image": {"data:image/jpg;url": "random_url"}, "other_data": "other_data"},
        }
        result = converter.convert_path_to_url_recursively(
            value, path_to_url_converter=lambda path: "https://example.com/logo.jpg"
        )
        assert result == expected_value
