import pytest

from promptflow.utils.str_utils import convert_to_dictionary, remove_prefix


@pytest.mark.unittest
class TestStrUtils:
    @pytest.mark.parametrize(
        "text, prefix, expected_value",
        [
            (None, None, None),
            ("hello world", None, "hello world"),
            ("hello world", "world", "hello world"),
            ("hello world", "hello ", "world"),
            ("hello world", "NonExistedPrefix", "hello world"),
            ("promptflow_0.0.1", "promptflow_", "0.0.1"),
            ("NoColumnsFoundError", "NoColumnsFoundError", ""),
        ],
    )
    def test_remove_prefix(self, text, prefix, expected_value):
        assert remove_prefix(text, prefix) == expected_value

    def test_convert_to_dictionary(self):
        assert convert_to_dictionary("locations/eastus2euap/data/test_asset/versions/1") == {
            "locations": "eastus2euap",
            "data": "test_asset",
            "versions": "1",
        }
        assert convert_to_dictionary("/key1/value1/") == {"key1": "value1"}
        assert convert_to_dictionary("  key1/value1  ") == {"key1": "value1"}

        invalid_text = "/paths/invalid/text"
        with pytest.raises(ValueError, match=f"Invalid text: {invalid_text}"):
            convert_to_dictionary(invalid_text)

        with pytest.raises(ValueError, match="Empty text"):
            convert_to_dictionary("")
