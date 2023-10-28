import pytest

from promptflow._utils.feature_utils import Feature, get_feature_list


@pytest.mark.unittest
def test_get_feature_list():
    feature_list = get_feature_list()
    assert isinstance(feature_list, list)
    assert all(isinstance(feature, Feature) for feature in feature_list)
