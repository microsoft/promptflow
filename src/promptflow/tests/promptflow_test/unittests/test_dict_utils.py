import pytest

from promptflow.utils.dict_utils import get_value_by_key_path

TEST_DICT = {
    "Earth": {
        "Asia": {
            "China": {
                "Beijing": {
                    "Haidian": {
                        "ZipCode": "110108",
                        "CreatedAt": "1952-09-01",
                    }
                },
                "Shenzhen": {
                    "Population": 12528300,
                    "City Trees": [
                        "Lychee",
                        "Mangrove",
                    ],
                },
            },
            "Japan": {
                "Tokyo": {
                    "Area": 219093,
                }
            },
        },
        "North America": {
            "USA": {
                "Washington": {
                    "Seattle": {
                        "Famous Company": "Microsoft",
                        "Website": "seattle.gov",
                    }
                }
            }
        },
    }
}


@pytest.mark.unittest
class TestDictUtils:
    @pytest.mark.parametrize(
        "key_path, expected_value",
        [
            ("Earth/Asia/China/Beijing/Haidian/ZipCode", "110108"),
            ("Earth/Asia/China/Shenzhen/Population", 12528300),
            ("Earth/Asia/China/Shenzhen/City Trees", ["Lychee", "Mangrove"]),
            ("Earth/Asia/Japan/Tokyo/Area", 219093),
            ("Earth/North America/USA/Washington/Seattle/Famous Company", "Microsoft"),
            ("Earth/North America/USA/Washington/Seattle/Website", "seattle.gov"),
        ],
    )
    def test_get_value_by_key_path_normal_case(self, key_path, expected_value):
        assert get_value_by_key_path(TEST_DICT, key_path) == expected_value

    def test_get_value_by_key_path_invalid_key_path(self):
        assert get_value_by_key_path(TEST_DICT, "Earth/Asia/China/Beijing/Chaoyang/ZipCode") is None
        assert get_value_by_key_path(TEST_DICT, "Earth/Asia/China/Beijing/Chaoyang/ZipCode", default_value="0") == "0"
        assert get_value_by_key_path(TEST_DICT, "Earth/Asia/China/Beijing/Haidian/Population") is None
        assert get_value_by_key_path(TEST_DICT, "Mars") is None

        with pytest.raises(ValueError, match="key_path must not be empty"):
            get_value_by_key_path(TEST_DICT, "")

    def test_get_value_from_empty_dict(self):
        assert get_value_by_key_path({}, "dummy/dummy") is None
        assert get_value_by_key_path(None, "dummy/dummy") is None

    @pytest.mark.parametrize(
        "dict, key_path, expected_value",
        [
            ({}, "dummy/dummy", "default"),
            (None, "dummy/dummy", "default"),
            (TEST_DICT, "Earth/Asia/Japan/Tokyo/Area", 219093),
            (TEST_DICT, "Earth/Asia/Japan/Tokyo", {"Area": 219093}),
            (TEST_DICT, "Earth/Asia/Japan/Tokyo/Area/NonExistKey", "default"),
            (TEST_DICT, "Earth/Asia/Japan/Tokyo/NonExistKey", "default"),
            (TEST_DICT, "Earth/Asia/Japan/NonExistKey", "default"),
        ],
    )
    def test_default_value(self, dict, key_path, expected_value):
        assert get_value_by_key_path(dict, key_path, default_value="default") == expected_value
