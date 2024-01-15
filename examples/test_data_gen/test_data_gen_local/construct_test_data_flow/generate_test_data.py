import os

from langchain.chat_models import AzureChatOpenAI
from langchain.embeddings import AzureOpenAIEmbeddings
from llama_index.schema import TextNode
from ragas.llms import LangchainLLM
from utils import TestsetGeneratorV2

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection


# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def my_python_tool(connection: AzureOpenAIConnection, document_node_str: str) -> dict:

    os.environ["AZURE_OPENAI_API_KEY"] = connection.api_key
    os.environ["AZURE_OPENAI_ENDPOINT"] = connection.api_base
    os.environ["OPENAI_API_VERSION"] = connection.api_version

    azure_model = AzureChatOpenAI(deployment_name="gpt-4", model="gpt-4")

    azure_embeddings = AzureOpenAIEmbeddings(deployment="text-embedding-ada-002", model="text-embedding-ada-002")

    generator_llm = LangchainLLM(llm=azure_model)
    critic_llm = LangchainLLM(llm=azure_model)
    embeddings_model = azure_embeddings

    testset_distribution = {
        "simple": 1,
        "reasoning": 0,
        "multi_context": 0,
        "conditional": 0,
    }

    test_generator = TestsetGeneratorV2(
        generator_llm=generator_llm,
        critic_llm=critic_llm,
        embeddings_model=embeddings_model,
        testset_distribution=testset_distribution,
        chat_qa=0,
    )

    # json_dict = json.dumps(document_node_str)
    document_node = TextNode.from_json(document_node_str)

    test_data = test_generator.generate(document_node=document_node)

    return test_data
