from promptflow.rag.resources import LocalSource, AzureAISearchConfig, EmbeddingsModelConfig, ConnectionConfig
from promptflow.rag import build_index


def main():
    local_index_local_files_index_name = "local-test-00"
    ai_search_index_path=build_index(
        name=local_index_local_files_index_name,  # name of your index
        vector_store="azure_ai_search",  # the type of vector store - in this case it is Azure AI Search. Users can also use "azure_cognitive_search"
        embeddings_model_config=EmbeddingsModelConfig(
            model_name="text-embedding-ada-002",
            deployment_name="text-embedding-ada-002",
            connection_config=ConnectionConfig(
                subscription = "f375b912-331c-4fc5-8e9f-2d7205e3e036",
                resource_group = "rg-jingyizhuai",
                workspace = "jingyizhu-project-2",
                connection_name = "jingyiaoai"
            )
        ),
        input_source=LocalSource(input_data="data/product-info/"),  # the location of your file/folders
        index_config=AzureAISearchConfig(
            ai_search_index_name=local_index_local_files_index_name + "-store", # the name of the index store inside the azure ai search service
            ai_search_connection_config=ConnectionConfig(
                subscription = "f375b912-331c-4fc5-8e9f-2d7205e3e036",
                resource_group = "rg-jingyizhuai",
                workspace = "jingyizhu-project-2",
                connection_name = "jingyiacsuk"
            )
        ),
        tokens_per_chunk = 800, # Optional field - Maximum number of tokens per chunk
        token_overlap_across_chunks = 0, # Optional field - Number of tokens to overlap between chunks
    )
    print(ai_search_index_path)

if __name__=="__main__": 
    main() 