import pytest

from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
from promptflow.core.connection_manager import ConnectionManager
from promptflow.tools.embedding import embedding


@pytest.fixture
def azure_open_ai_connection() -> [AzureOpenAIConnection]:
    return ConnectionManager().get("azure_open_ai_connection")


@pytest.fixture
def open_ai_connection() -> [OpenAIConnection]:
    return ConnectionManager().get("open_ai_connection")


@pytest.mark.usefixtures("use_secrets_config_file", "azure_open_ai_connection",
                         "open_ai_connection")
class TestEmbedding:
    def test_aoai_embedding_api(self, azure_open_ai_connection):
        input = ["The food was delicious and the waiter"]  # we could use array as well, vs str
        result = embedding(azure_open_ai_connection, input=input, deployment_name="text-embedding-ada-002")
        embedding_vector = ", ".join(str(num) for num in result)
        print("embedding() api result=[" + embedding_vector + "]")

    @pytest.mark.skip(reason="openai key not set yet")
    def test_openai_embedding_api(self, open_ai_connection):
        input = ["The food was delicious and the waiter"]  # we could use array as well, vs str
        result = embedding(open_ai_connection, input=input, model="text-embedding-ada-002")
        embedding_vector = ", ".join(str(num) for num in result)
        print("embedding() api result=[" + embedding_vector + "]")
