import pytest

from promptflow.executor._docstring_parser import DocstringParser


@pytest.mark.unittest
class TestDocstringParser:
    def test_description_extract(self):

        # Single line description
        docstring = """
        Hello world.

        :param name: The name to be say thanks to.
        :type name: str
        :param connection: The connection to Azure OpenAI.
        :type connection: AzureOpenAIConnection
        """

        expected_des = "Hello world."
        assert expected_des == DocstringParser.parse_description(docstring)

        # Multiple lines of description

        docstring = """
        Generate thanks statement over multiple lines
        with additional details. This part should also be included in the description.

        :param name: The name to be say thanks to.
        :type name: str
        :param connection: The connection to Azure OpenAI.
        :type connection: AzureOpenAIConnection
        """

        expected_des = (
            "Generate thanks statement over multiple lines\n"
            "with additional details. This part should also be included in the description."
        )
        assert expected_des == DocstringParser.parse_description(docstring)

        # Multiple lines of description

        docstring = """
        line 1.

        line2.

        :param name: The name to be say thanks to.
        :type name: str
        :param connection: The connection to Azure OpenAI.
        :type connection: AzureOpenAIConnection
        """

        expected_des = "line 1. line2."
        assert expected_des == DocstringParser.parse_description(docstring)

        # Multiple lines of description

        docstring = """
        line 1

        line2

        :param name: The name to be say thanks to.
        :type name: str
        :param connection: The connection to Azure OpenAI.
        :type connection: AzureOpenAIConnection
        """

        expected_des = "line 1 line2"
        assert expected_des == DocstringParser.parse_description(docstring)

        docstring = """
        line 1

        line2.

        :param name: The name to be say thanks to.
        :type name: str
        :param connection: The connection to Azure OpenAI.
        :type connection: AzureOpenAIConnection
        """

        expected_des = "line 1 line2."
        assert expected_des == DocstringParser.parse_description(docstring)

        docstring = """
        line 1
        line2.

        :param name: The name to be say thanks to.
        :type name: str
        :param connection: The connection to Azure OpenAI.
        :type connection: AzureOpenAIConnection
        """

        expected_des = "line 1\nline2."
        assert expected_des == DocstringParser.parse_description(docstring)
