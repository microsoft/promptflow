# How to use enabled by in the tool package
## Introduction
This guide will instruct you on how to use the "enabled by" feature in the tool package. The "enabled by" feature is designed to display which inputs are enabled when a customer uses a specific input type or input value. This feature is particularly useful if you need to adapt your inputs based on varying requirements.

We introduce parameter "enabled_by" in the tool yaml to determine which input is enabled by which other input.
Concurrently, we support enabling an input by another input type or input value, Hence, we introduce two additional parameters: "enabled_by_type" and "enabled_by_value".

> Note: We do not recommend using 'enabled_by_type' and 'enabled_by_value' simultaneously. If both are used, 'enabled_by_type' will be ignored.

## Prerequisites
To proceed, it's crucial for you to understand the process of developing a tool and generating a tool yaml. For thorough insights and instructions, please refer to [Create and Use Tool Package](create-and-use-tool-package.md). 

## How to support enabled by
Assume you want to develop a tool with four inputs: "connection", "input", "deployment_name", and "model". The "deployment_name" and "model" are enabled by "connection" type. When the "connection" type is AzureOpenAIConnection, the "deployment_name" input is enabled and displayed. When the "connection" type is OpenAIConnection, the "model" input is enabled and displayed. You need to support enable by in two part: tool and tool yaml. Here is an example of how you can support the "enabled by" feature in your tool and tool yaml.


### Step 1: Support "enabled by" in the tool
All inputs will be passed to the tool, allowing you to define your own set of rules to determine which input to use. Here is an example of how you can support the "enabled by" feature in your tool:


```python
from enum import Enum
from typing import Union

import openai

from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
from promptflow._internal import tool
from promptflow.tools.exception import InvalidConnectionType


class EmbeddingModel(str, Enum):
    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"
    TEXT_SEARCH_ADA_DOC_001 = "text-search-ada-doc-001"
    TEXT_SEARCH_ADA_QUERY_001 = "text-search-ada-query-001"


@tool
def embedding(connection: Union[AzureOpenAIConnection, OpenAIConnection], input: str, deployment_name: str = "", model: EmbeddingModel = EmbeddingModel.TEXT_EMBEDDING_ADA_002):
    connection_dict = dict(connection)
    # If the connection type is AzureOpenAIConnection, use the deployment_name input.
    if isinstance(connection, AzureOpenAIConnection):
        return openai.Embedding.create(
            input=input,
            engine=deployment_name,
            **connection_dict,
        )["data"][0]["embedding"]
    # If the connection type is OpenAIConnection, use the model input.
    elif isinstance(connection, OpenAIConnection):
        return openai.Embedding.create(
            input=input,
            model=model,
            **connection_dict,
        )["data"][0]["embedding"]
    else:
        error_message = f"Not Support connection type '{type(connection).__name__}' for embedding api. " \
                        f"Connection type should be in [AzureOpenAIConnection, OpenAIConnection]."
        raise InvalidConnectionType(message=error_message)
```

### Step 2: Support "enabled by" in the tool yaml
Once you have generated a tool yaml, you can incorporate the 'enabled by' feature into it. Here is an example showcasing the use of 'enabled_by_type' in the tool yaml:

```yaml
promptflow.tools.embedding.embedding:
  name: Embedding
  description: Use Open AI's embedding model to create an embedding vector representing the input text.
  type: python
  module: promptflow.tools.embedding
  function: embedding
  inputs:
    connection:
      type: [AzureOpenAIConnection, OpenAIConnection]
    deployment_name:
      type:
      - string
      # The input deployment_name is enabled by connection
      enabled_by: connection
      # When the connection type is AzureOpenAIConnection, deployment_name is enabled and displayed.
      enabled_by_type: [AzureOpenAIConnection]
      capabilities:
        completion: false
        chat_completion: false
        embeddings: true
      model_list:
      - text-embedding-ada-002
      - text-search-ada-doc-001
      - text-search-ada-query-001
    model:
      type:
      - string
      # The input model is enabled by connection
      enabled_by: connection
      # When the connection type is OpenAIConnection, model is enabled and displayed.
      enabled_by_type: [OpenAIConnection]
      enum:
      - text-embedding-ada-002
      - text-search-ada-doc-001
      - text-search-ada-query-001
    input:
      type:
      - string
```

> Note: Both "enabled_by_type" and "enabled_by_value" are list types, which means you can use multiple inputs to enable a single input. For instance, if "enabled_by_type" is [AzureOpenAIConnection, OpenAIConnection], the input will be enabled when the connection type is either AzureOpenAIConnection or OpenAIConnection.

After you build and share the tool package generated with the above steps, you can use your tool from VSCode Extension. When you select a connection with azure openai type, only deployment_name input is enabled and displayed.

![enabled_by_type.png](../../media/how-to-guides/develop-a-tool/enabled_by_type.png)
