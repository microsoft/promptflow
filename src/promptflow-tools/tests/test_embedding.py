import pytest

from promptflow.exceptions import ErrorResponse
from promptflow.tools.embedding import embedding
from promptflow.tools.exception import InvalidConnectionType


@pytest.mark.usefixtures("use_secrets_config_file")
class TestEmbedding:
    def test_embedding_conn_aoai(self, azure_open_ai_connection):
        result = embedding(
            connection=azure_open_ai_connection,
            input="The food was delicious and the waiter",
            deployment_name="text-embedding-ada-002")
        assert len(result) == 1536

    @pytest.mark.skip_if_no_key("open_ai_connection")
    def test_embedding_conn_oai(self, open_ai_connection):
        result = embedding(
            connection=open_ai_connection,
            input="The food was delicious and the waiter",
            model="text-embedding-ada-002")
        assert len(result) == 1536

    def test_embedding_invalid_connection_type(self, serp_connection):
        with pytest.raises(InvalidConnectionType) as exc_info:
            embedding(connection=serp_connection, input="hello", deployment_name="text-embedding-ada-002")
        assert "UserError/ToolValidationError/InvalidConnectionType" == ErrorResponse.from_exception(
            exc_info.value).error_code_hierarchy
