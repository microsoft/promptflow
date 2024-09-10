# Rerank

## Introduction
Rerank is a semantic search tool that improves search quality with a semantic-based reranking system which can contextualize the meaning of a user's query beyond keyword relevance. This tool works best with look up tool as a ranker after the initial retrieval. The list of current supported ranking method is as follows.

| Name | Description |
| --- | --- |
| BM25 | BM25 is an open source ranking algorithm to measure the relevance of documents to a given query |
| Scaled Score Fusion | Scaled Score Fusion calculates a scaled relevance score. |
| Cohere Rerank | Cohere Rerank is the market’s leading reranking model used for semantic search and retrieval-augmented generation (RAG). |

## Requirements
- For AzureML users, the tool is installed in default image, you can use the tool without extra installation.
- For local users,

  `pip install promptflow-vectordb`

## Prerequisites

BM25 and Scaled Score Fusion are included as default reranking methods. To use cohere rerank model, you should create serverless deployment to the model, and establish connection between the tool and the resource as follows.

- Add Serverless Model connection. Fill "API base" and "API key" field to your serverless deployment.


## Inputs

|  Name                  | Type        | Description                                                           | Required |
|------------------------|-------------|-----------------------------------------------------------------------|----------|
| query                  | string      | the question relevant to your input documents                         | Yes      |
| ranker_parameters      | string      | the type of ranking methods to use                                    | Yes      |
| result_groups          | object      | the list of document chunks to rerank. Normally this is output from lookup | Yes      |
| top_k                  | int         | the maximum number of relevant documents to return                    | No      |



## Outputs

| Return Type | Description                              |
|-------------|------------------------------------------|
| text        | text of the entity |
| metadata    | metadata like file path and url |
| additional_fields    | metadata and rerank score |

  <details>
    <summary>Output</summary>
    
  ```json
  [
    {
        "text": "sample text",
        "metadata":
        {
            "filepath": "sample_file_path",
            "metadata_json_string": "meta_json_string"
            "title": "",
            "url": ""
        },
        "additional_fields":
        {
            "filepath": "sample_file_path",
            "metadata_json_string": "meta_json_string"
            "title": "",
            "url": "",
            "@promptflow_vectordb.reranker_score": 0.013795365
        }
    }
  ]
  ```
  </details>