---
title: Index lookup tool for flows in Azure AI Studio
titleSuffix: Azure AI Studio
description:  This article introduces the Index Lookup tool for flows in Azure AI Studio.
author: e-straight
manager: nitinme
ms.service: azure-ai-studio
ms.topic: conceptual
ms.date: 01/18/2024
ms.author: eur
---

# Index Lookup tool for Azure AI Studio

[!INCLUDE [Azure AI Studio preview](../../includes/preview-ai-studio.md)]

The prompt flow *Index Lookup* tool enables the usage of common vector indices (such as Azure AI Search, FAISS, and Pinecone) for retrieval augmented generation (RAG) in prompt flow. The tool automatically detects the indices in the workspace and allows the selection of the index to be used in the flow.

## Build with the Index Lookup tool

1. Create or open a flow in Azure AI Studio. For more information, see [Create a flow](../flow-develop.md).
1. Select **+ More tools** > **Index Lookup** to add the Index Lookup tool to your flow.

    :::image type="content" source="../../media/prompt-flow/configure-index-lookup-tool.png" alt-text="Screenshot of the Index Lookup tool added to a flow in Azure AI Studio." lightbox="../../media/prompt-flow/configure-index-lookup-tool.png":::

1. Enter values for the Index Lookup tool [input parameters](#inputs). The [LLM tool](llm-tool.md) can generate the vector input.
1. Add more tools to your flow as needed, or select **Run** to run the flow.
1. To learn more about the returned output, see [outputs](#outputs).


## Inputs

The following are available input parameters:

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| mlindex_content | string | Type of index to be used. Input depends on the index type. An example of an Azure AI Search index JSON can be seen below the table. | Yes |
| queries | string, `Union[string, List[String]]` | The text to be queried.| Yes |
|query_type | string | The type of query to be performed. Options include Keyword, Semantic, Hybrid, and others.  | Yes |
| top_k | integer | The count of top-scored entities to return. Default value is 3. | No |

Here's an example of an Azure AI Search index input.

```json
embeddings:
  api_base: <api_base>
  api_type: azure
  api_version: 2023-07-01-preview
  batch_size: '1'
  connection:
    id: /subscriptions/<subscription>/resourceGroups/<resource_group>/providers/Microsoft.MachineLearningServices/workspaces/<workspace> /connections/<AOAI_connection>
  connection_type: workspace_connection
  deployment: <embedding_deployment>
  dimension: <embedding_model_dimension>
  kind: open_ai
  model: <embedding_model>
  schema_version: <version>
index:
  api_version: 2023-07-01-Preview
  connection:
    id: /subscriptions/<subscription>/resourceGroups/<resource_group>/providers/Microsoft.MachineLearningServices/workspaces/<workspace> /connections/<cogsearch_connection>
  connection_type: workspace_connection
  endpoint: <cogsearch_endpoint>
  engine: azure-sdk
  field_mapping:
    content: id
    embedding: content_vector_open_ai
    metadata: id
  index: <index_name>
  kind: acs
  semantic_configuration_name: azureml-default
```

## Outputs

The following JSON format response is an example returned by the tool that includes the top-k scored entities. The entity follows a generic schema of vector search result provided by the `promptflow-vectordb` SDK. For the Vector Index Search, the following fields are populated:

| Field Name | Type | Description |
| ---- | ---- | ----------- |
| metadata | dict | Customized key-value pairs provided by user when creating the index |
| page_content | string | Content of the vector chunk being used in the lookup |
| score | float | Depends on index type defined in Vector Index. If index type is Faiss, score is L2 distance. If index type is Azure AI Search, score is cosine similarity. |


  
```json
[
  {
    "metadata":{
      "answers":{},
      "captions":{
        "highlights":"sample_highlight1",
        "text":"sample_text1"
      },
      "page_number":44,
      "source":{
        "filename":"sample_file1.pdf",
        "mtime":1686329994,
        "stats":{
          "chars":4385,
          "lines":41,
          "tiktokens":891
        },
        "url":"sample_url1.pdf"
      },
      "stats":{
        "chars":4385,"lines":41,"tiktokens":891
      }
    },
    "page_content":"vector chunk",
    "score":0.021349556744098663
  },

  {
    "metadata":{
      "answers":{},
      "captions":{
        "highlights":"sample_highlight2",
        "text":"sample_text2"
      },
      "page_number":44,
      "source":{
        "filename":"sample_file2.pdf",
        "mtime":1686329994,
        "stats":{
          "chars":4385,
          "lines":41,
          "tiktokens":891
        },
        "url":"sample_url2.pdf"
      },
      "stats":{
        "chars":4385,"lines":41,"tiktokens":891
      }
    },
    "page_content":"vector chunk",
    "score":0.021349556744098663
  },
    
]

```


## How to migrate from legacy tools to the Index Lookup tool
The Index Lookup tool looks to replace the three deprecated legacy index tools, the [Vector Index Lookup tool](./vector-index-lookup-tool.md), the [Vector DB Lookup tool](./vector-db-lookup-tool.md) and the [Faiss Index Lookup tool](./faiss-index-lookup-tool.md).
If you have a flow that contains one of these tools, follow the steps below to upgrade your flow.

### Upgrade your tools

1. Update your runtime. In order to do this navigate to the "AI project settings tab on the left blade in AI Studio. From there you should see a list of Prompt flow runtimes. Select the name of the runtime you want to update, and click on the “Update” button near the top of the panel. Wait for the runtime to update itself.
1. Navigate to your flow. You can do this by clicking on the “Prompt flow” tab on the left blade in AI Studio, clicking on the “Flows” pivot tab, and then clicking on the name of your flow. 

1. Once inside the flow, click on the “+ More tools” button near the top of the pane. A dropdown should open and click on “Index Lookup [Preview]” to add an instance of the Index Lookup tool.

   :::image type="content" source="../../media/prompt-flow/upgrade-index-tools/index-dropdown.png" alt-text="Screenshot of the More Tools dropdown in promptflow." lightbox="../../media/prompt-flow/upgrade-index-tools/index-dropdown.png":::

1. Name the new node and click  “Add”.

   :::image type="content" source="../../media/prompt-flow/upgrade-index-tools/save-node.png" alt-text="Screenshot of the index lookup node with name." lightbox="../../media/prompt-flow/upgrade-index-tools/save-node.png":::

1. In the new node, click on the “mlindex_content” textbox. This should be the first textbox in the list.

   :::image type="content" source="../../media/prompt-flow/upgrade-index-tools/mlindex-box.png" alt-text="Screenshot of the expanded Index Lookup node with the mlindex_content box outlined in red." lightbox="../../media/prompt-flow/upgrade-index-tools/mlindex-box.png":::

1. In the Generate drawer that appears, follow the instructions below to upgrade from the three legacy tools:
- If using the legacy **Vector Index Lookup** tool, select “Registered Index" in the “index_type” dropdown. Select your vector index asset from the “mlindex_asset_id” dropdown.
- If using the legacy **Faiss Index Lookup** tool, select “Faiss” in the “index_type” dropdown and specify the same path as in the legacy tool.
- If using the legacy **Vector DB Lookup** tool, select AI Search or Pinecone depending on the DB type in the “index_type” dropdown and fill in the information as necessary.
8. After filling in the necessary information, click save. 
9. Upon returning to the node, there should be information populated in the “mlindex_content” textbox. Click on the “queries” textbox next, and select the search terms you want to query. You’ll want to select the same value as the input to the “embed_the_question” node, typically either “\${inputs.question}” or “${modify_query_with_history.output}” (the former if you’re in a standard flow and the latter if you’re in a chat flow).

   :::image type="content" source="../../media/prompt-flow/upgrade-index-tools/mlindex-with-content.png" alt-text="Screenshot of the expanded Index Lookup node with index information in the cells." lightbox="../../media/prompt-flow/upgrade-index-tools/mlindex-with-content.png":::

10. Select a query type by clicking on the dropdown next to “query_type.” “Vector” will produce identical results as the legacy flow, but depending on your index configuration, other options including "Hybrid" and "Semantic" may be available.

    :::image type="content" source="../../media/prompt-flow/upgrade-index-tools/vector-search.png" alt-text="Screenshot of the expanded Index Lookup node with vector search outlined in red." lightbox="../../media/prompt-flow/upgrade-index-tools/vector-search.png":::

11. Edit downstream components to consume the output of your newly added node, instead of the output of the legacy Vector Index Lookup node. 
12. Delete the Vector Index Lookup node and its parent embedding node. 

## Next steps

- [Learn more about how to create a flow](../flow-develop.md)
