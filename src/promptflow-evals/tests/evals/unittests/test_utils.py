import pytest

from promptflow.evals._common.utils import nltk_tokenize


@pytest.mark.unittest
class TestUtils:
    def test_nltk_tokenize(self):

        # Test with English text
        text = "The capital of China is Beijing."
        tokens = nltk_tokenize(text)

        assert tokens == ["The", "capital", "of", "China", "is", "Beijing", "."]

        # Test with Multi-language text
        text = "The capital of China is 北京."
        tokens = nltk_tokenize(text)

        assert tokens == ["The", "capital", "of", "China", "is", "北京", "."]
