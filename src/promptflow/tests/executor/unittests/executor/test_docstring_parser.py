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

        expected_des = "Hello world.\n"
        assert expected_des == DocstringParser.parse_description(docstring)[0]

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
        assert expected_des == DocstringParser.parse_description(docstring)[0]

        # Multiple lines of description

        docstring = """
        line 1.

        line 2.

        :param name: The name to be say thanks to.
        :type name: str
        :param connection: The connection to Azure OpenAI.
        :type connection: AzureOpenAIConnection
        """

        expected_des = "line 1.\n\nline 2."
        assert expected_des == DocstringParser.parse_description(docstring)[0]

        # Multiple lines of description

        docstring = """
        line 1

        line 2

        :param name: The name to be say thanks to.
        :type name: str
        :param connection: The connection to Azure OpenAI.
        :type connection: AzureOpenAIConnection
        """

        expected_des = "line 1\n\nline 2"
        assert expected_des == DocstringParser.parse_description(docstring)[0]

        docstring = """
        line 1

        line 2.

        :param name: The name to be say thanks to.
        :type name: str
        :param connection: The connection to Azure OpenAI.
        :type connection: AzureOpenAIConnection
        """

        expected_des = "line 1\n\nline 2."
        assert expected_des == DocstringParser.parse_description(docstring)[0]

        docstring = """
        line 1
        line 2.

        :param name: The name to be say thanks to.
        :type name: str
        :param connection: The connection to Azure OpenAI.
        :type connection: AzureOpenAIConnection
        """

        expected_des = "line 1\nline 2."
        assert expected_des == DocstringParser.parse_description(docstring)[0]

        docstring = """

        :param name: The name to be say thanks to.
        :type name: str
        :param connection: The connection to Azure OpenAI.
        :type connection: AzureOpenAIConnection
        """

        expected_des = ""
        assert expected_des == DocstringParser.parse_description(docstring)[0]

    def test_param_description_extract(self):

        # Type section is missing
        docstring = """
        Hello world.

        :param name: The name to be say thanks to.
        :param connection: The connection to Azure OpenAI.
        :type connection: AzureOpenAIConnection
        """

        params = DocstringParser.parse_description(docstring)[1]
        assert len(params) == 2
        assert params["name"]["description"] == "The name to be say thanks to."
        assert params["connection"]["description"] == "The connection to Azure OpenAI."

        # Description section is missing
        docstring = """
               Hello world.

               :type name: str
               :param connection: The connection to Azure OpenAI.
               :type connection: AzureOpenAIConnection
               """

        params = DocstringParser.parse_description(docstring)[1]
        assert len(params) == 1
        assert "name" not in params
        assert params["connection"]["description"] == "The connection to Azure OpenAI."

        # Description section is missing
        docstring = """
               Hello world.

               """

        params = DocstringParser.parse_description(docstring)[1]
        assert len(params) == 0
