# Trace Span Specification

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../how-to-guides/faq.md#stable-vs-experimental).
:::

This document outlines the design of Prompt flow spans, detailing what information is traced and how it is structured.

## Introduction

The span, as you may know, is the fundamental unit of the trace system, representing a unit that captures execution information in the Prompt flow system. Spans are nested together in a parent-child relationship and paired together by link relationships, providing developers and users with a comprehensive view of the application’s execution process.

By adhering to these specifications, we ensure transparency and consistency in our tracing system.

The UI interprets the captured spans and presents them in a user-friendly manner. Understanding the fields and contracts defined within the spans is essential for effectively utilizing Prompt flow or integrating its components.

## OpenTelemetry Span Basics

A typical span object contains below information:

| Field | Description |
|---|---|
| name | Name of span |
| parent_id | Parent span ID (empty for root spans) |
| context | [Span Context](https://opentelemetry.io/docs/concepts/signals/traces/#span-context) |
| start_time | Start time of the span |
| end_time | End time of the span |
| status | [Span Status](https://opentelemetry.io/docs/concepts/signals/traces/#span-status) |
| attributes | [Attributes](https://opentelemetry.io/docs/concepts/signals/traces/#attributes) |
| events | [Span Events](https://opentelemetry.io/docs/concepts/signals/traces/#span-events) |
| links | [Span Links](https://opentelemetry.io/docs/concepts/signals/traces/#span-links) |

## Span in Prompt flow

In Prompt flow, we define several span types, and the system automatically creates spans with execution information in designated attributes and events.

These span types share common attributes and events, which we refer to as standard attributes and events. Let’s explore these common elements before diving into the specifics of each span type.

### Common Attributes and Events

#### Attributes

Each span in Prompt flow is enriched with a set of standard attributes that provide essential information about the span's context and purpose. The following table outlines these attributes:

| Attribute | Type | Description | Examples | [Requirement Level](https://opentelemetry.io/docs/specs/semconv/general/attribute-requirement-level/) |
|---|---|---|---|---|
| framework | string | This attribute specifies the framework in which the trace was recorded. For our project, this value is consistently set to promptflow.  | promptflow | `Required` |
| node_name | string | Denotes the name of the flow node. | chat | `Conditionally Required` if the flow is a Directed Acyclic Graph ([DAG](../concepts/concept-flows.md#dag-flow)) flow. |
| span_type | string | Specifies the type of span, such as LLM or Flow. See [this](#span-types-specification) for details. | LLM | `Required` |
| line_run_id | string | Unique identifier for the execution run within Prompt flow. | d23159d5-cae0-4de6-a175-295c715ce251 | `Required` |
| function | string | The function associated with the span. | search | `Recommended` |
| session_id | string | Unique identifier for chat sessions. | 4ea1a462-7617-439f-a40c-12a8b93f51fb | `Opt-In` |
| referenced.line_run_id | string | Represents the line run ID that is the source of the evaluation run. | f747f7b8-983c-4bf2-95db-0ec3e33d4fd1 | `Conditionally Required` only used in evaluation runs - runs on [evaluation flow](../concepts/concept-flows.md#flow-types).|
| batch_run_id | string | The batch run ID when in batch mode. | 61daff70-80d5-4e79-a50b-11b38bb3d344 | `Conditionally Required` only used in batch runs. |
| referenced.batch_run_id | string | Notes the batch run ID against which an evaluation flow ran. | 851b32cb-545c-421d-8e51-0a3ea66f0075 | `Conditionally Required` only used in evaluation runs. |
| line_number | int | The line number within a batch run, starting from 0. | `1` | `Conditionally Required` only used in batch runs. |
| \_\_computed\_\_.cumulative_token_count.prompt | int | Cumulative token count of child nodes for prompts. [1] | `200` | `Recommended` |
| \_\_computed\_\_.cumulative_token_count.completion | int | Cumulative token count of child nodes for completion responses. [1] | `80` | `Recommended` |
| \_\_computed\_\_.cumulative_token_count.total | int | Total cumulative token count for both prompts and completions. [1] | `120` | `Recommended` |

**[1]:** Cumulative token counts are propagated up the span hierarchy, ensuring each span reflects the total token count of all LLM executions within its scope.

#### Events

In Prompt flow, events emitted by the Prompt flow framework follow the format below

- event MUST has attributes
- event attributes MUST contain a key named `payload`, which refers to the data carried within an event.
- event attributes payload MUST be a JSON string that represent an object.

| Event | Payload Description | Payload Examples | [Requirement Level](https://opentelemetry.io/docs/specs/semconv/general/attribute-requirement-level/) |
|---|---|---|---|
| promptflow.function.inputs | Input of a function call | ```{"chat_history":[],"question":"What is ChatGPT?"}``` | `Required` |
| promptflow.function.output | Output of a function call | ```{"answer":"ChatGPT is a conversational AI model developed by OpenAI."}``` | `Required` |

### Span Types Specification

Within the Prompt flow system, we have delineated several distinct span types to cater to various execution units. Each span type is designed to capture specific execution information, complementing the standard attributes and events. Currently, our system includes the following span types: `LLM`, `Function`, `LangChain`, `Flow`, `Embedding` and `Retrieval`.

Beyond the standard attributes and events, each span type possesses designated fields to store pertinent information unique to its role within the system. These specialized attributes and events ensure that all relevant data is meticulously traced and available for analysis.

#### LLM

The LLM (Large Language Model) span captures detailed execution information from calls to large language models.

| Attribute | Type | Description | Examples | [Requirement Level](https://opentelemetry.io/docs/specs/semconv/general/attribute-requirement-level/) |
|---|---|---|---|---|
| span_type | string | Identifies the span as an LLM type. | LLM | `Required` |
| llm.usage.total_tokens | int | Total number of tokens used, including both prompt and response. | `180` | `Required` |
| llm.usage.prompt_tokens | int | Number of tokens used in the LLM prompt. | `100` | `Required` |
| llm.usage.completion_tokens | int | Number of tokens used in the LLM response (completion). | `80` | `Required` |
| llm.response.model | string | Specifies the LLM that generated the response. | gpt-4 | `Required` |

| Event | Payload Description | Payload Examples | Requirement Level |
|---|---|---|---|
| promptflow.llm.generated_message | Captures the output message from an LLM call. | ```{"content":"ChatGPT is a conversational AI model developed by OpenAI.","role":"assistant","function_call":null,"tool_calls":null}``` | `Required` |

>Note: OpenTelemetry currently defines several LLM-related span attributes and events as semantic conventions. We plan to align with these conventions in the future. For more information, visit [Semantic Conventions for GenAI operations](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-spans.md).

#### Function

The Function span is a versatile default span within Prompt flow, designed to capture a wide range of general function execution information.

| Attribute | Type | Description | Examples | [Requirement Level](https://opentelemetry.io/docs/specs/semconv/general/attribute-requirement-level/) |
|---|---|---|---|---|
| span_type | string | Identifies the span as a Function type. | Function | `Required` |


| Event | Payload Description | Payload Examples | [Requirement Level](https://opentelemetry.io/docs/specs/semconv/general/attribute-requirement-level/) |
|---|---|---|---|
| promptflow.prompt.template | Details the prompt template and variable information. | ```{"prompt.template":"# system:\nYou are a helpful assistant.\n\n# user:\n{{question}}","prompt.variables":"{\n "question": "What is ChatGPT?"\n}"}``` | `Conditionally Required` if the function contains prompt template formating. [1] |

**[1]**: Template formatting is a process by resolving prompt template into prompt message, this process can happen within a function that invokes LLM call. 

#### Flow

The Flow span encapsulates the execution details of a flow within Prompt flow.

| Attribute | Type | Description | Examples | [Requirement Level](https://opentelemetry.io/docs/specs/semconv/general/attribute-requirement-level/) |
|---|---|---|---|---|
| span_type | string | Designates the span as a Flow type. | Flow | `Required` |

#### Embedding

The Embedding span is dedicated to recording the details of embedding calls within Prompt flow.

| Attribute | Type | Description | Examples | [Requirement Level](https://opentelemetry.io/docs/specs/semconv/general/attribute-requirement-level/) |
|---|---|---|---|---|
| span_type | string | Denotes the span as an Embedding type. | Embedding | `Required` |
| llm.usage.total_tokens | int | Total number of tokens used, sum of prompt and response tokens. | `180` | `Required` |
| llm.usage.prompt_tokens | int | Number of tokens used in the prompt for the embedding call. | `100` | `Required` |
| llm.usage.completion_tokens | int | Number of tokens used in the response from the embedding call. | `80` | `Required` |
| llm.response.model | string | Identifies the LLM model used for generating the embedding. | text-embedding-ada-002 | `Required` |

| Event | Payload Description | Payload Examples | [Requirement Level](https://opentelemetry.io/docs/specs/semconv/general/attribute-requirement-level/) |
|---|---|---|---|
| promptflow.embedding.embeddings | Details the embeddings generated by a call. | ```[{"embedding.vector":"","embedding.text":"When does a pipeline job reuse a previous job's results in Azure Machine Learning?"}]``` | `Required` |

#### Retrieval

The Retrieval span type is specifically designed to encapsulate the execution details of a retrieval task within Prompt flow.

| Attribute | Type | Description | Examples | [Requirement Level](https://opentelemetry.io/docs/specs/semconv/general/attribute-requirement-level/) |
|---|---|---|---|---|
| span_type | string | Labels the span as a Retrieval type. | Retrieval | `Required` |

| Event | Payload Description | Payload Examples | [Requirement Level](https://opentelemetry.io/docs/specs/semconv/general/attribute-requirement-level/) |
|---|---|---|---|
| promptflow.retrieval.query | Captures the text of the retrieval query. | ```"When does a pipeline job reuse a previous job's results in Azure Machine Learning?"``` | `Required` |
| promptflow.retrieval.documents | Details the list of retrieved documents relevant to the query. | ```[{"document.id":"https://componentsdk.azurewebsites.net/howto/caching-reuse.html","document.score":2.677619457244873,"document.content":"# Component concepts &..."},{"document.id":"https://learn.microsoft.com/en-us/azure/machine-learning/v1/reference-pipeline-yaml","document.score":2.563112735748291,"document.content":"etc. \|\r\n\| runconfig \| T..."}]``` | `Required` |
