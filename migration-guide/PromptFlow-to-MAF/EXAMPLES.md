# Migrated Flow Examples

We have generated migrated flows under the [`examples/flows/`](../../examples/flows/) folder for your reference. Each original Prompt Flow (PF) flow has a corresponding Microsoft Agent Framework (MAF) version (suffixed with `-maf`). The MAF workflows were created by AI using the [migration skill](../../.github/skills/promptflow-to-maf/).

---

## Chat Flows

| Example | PF Version | MAF Version | Description |
|---|---|---|---|
| Chat Basic | [chat-basic](../../examples/flows/chat/chat-basic/) | [chat-basic-maf](../../examples/flows/chat/chat-basic-maf/) | Chatbot that remembers previous interactions and generates responses using conversation history |
| Chat Math Variant | [chat-math-variant](../../examples/flows/chat/chat-math-variant/) | [chat-math-variant-maf](../../examples/flows/chat/chat-math-variant-maf/) | Prompt tuning example with three variants for testing math question answering approaches |
| Chat with Image | [chat-with-image](../../examples/flows/chat/chat-with-image/) | [chat-with-image-maf](../../examples/flows/chat/chat-with-image-maf/) | Chatbot that accepts both image and text as input using GPT-4V |
| Chat with PDF | [chat-with-pdf](../../examples/flows/chat/chat-with-pdf/) | [chat-with-pdf-maf](../../examples/flows/chat/chat-with-pdf-maf/) | Ask questions about PDF content using retrieval-augmented generation |
| Chat with Wikipedia | [chat-with-wikipedia](../../examples/flows/chat/chat-with-wikipedia/) | [chat-with-wikipedia-maf](../../examples/flows/chat/chat-with-wikipedia-maf/) | Chatbot with conversation history that searches Wikipedia for current information |
| Promptflow Copilot | [promptflow-copilot](../../examples/flows/chat/promptflow-copilot/) | [promptflow-copilot-maf](../../examples/flows/chat/promptflow-copilot-maf/) | Chat flow for building a copilot assistant for Promptflow |
| Use Functions with Chat Models | [use_functions_with_chat_models](../../examples/flows/chat/use_functions_with_chat_models/) | [use_functions_with_chat_models-maf](../../examples/flows/chat/use_functions_with_chat_models-maf/) | Extend LLM capabilities with external function specifications for chat models |

## Standard Flows

| Example | PF Version | MAF Version | Description |
|---|---|---|---|
| Autonomous Agent | [autonomous-agent](../../examples/flows/standard/autonomous-agent/) | [autonomous-agent-maf](../../examples/flows/standard/autonomous-agent-maf/) | AutoGPT agent that autonomously figures out how to apply functions to solve goals |
| Basic | [basic](../../examples/flows/standard/basic/) | [basic-maf](../../examples/flows/standard/basic-maf/) | Basic flow using custom Python tool calling Azure OpenAI with environment variables |
| Basic with Built-in LLM | [basic-with-builtin-llm](../../examples/flows/standard/basic-with-builtin-llm/) | [basic-with-builtin-llm-maf](../../examples/flows/standard/basic-with-builtin-llm-maf/) | Basic flow calling Azure OpenAI using the built-in LLM tool |
| Basic with Connection | [basic-with-connection](../../examples/flows/standard/basic-with-connection/) | [basic-with-connection-maf](../../examples/flows/standard/basic-with-connection-maf/) | Basic flow using custom Python tool with connection info stored in custom connection |
| Conditional Flow (If-Else) | [conditional-flow-for-if-else](../../examples/flows/standard/conditional-flow-for-if-else/) | [conditional-flow-for-if-else-maf](../../examples/flows/standard/conditional-flow-for-if-else-maf/) | Conditional flow that checks content safety and routes accordingly |
| Conditional Flow (Switch) | [conditional-flow-for-switch](../../examples/flows/standard/conditional-flow-for-switch/) | [conditional-flow-for-switch-maf](../../examples/flows/standard/conditional-flow-for-switch-maf/) | Conditional flow that dynamically routes by classifying user intent |
| Customer Intent Extraction | [customer-intent-extraction](../../examples/flows/standard/customer-intent-extraction/) | [customer-intent-extraction-maf](../../examples/flows/standard/customer-intent-extraction-maf/) | Identify customer intent from customer questions using LLM |
| Describe Image | [describe-image](../../examples/flows/standard/describe-image/) | [describe-image-maf](../../examples/flows/standard/describe-image-maf/) | Flow that flips an image horizontally and describes it using GPT-4V |
| Flow with Additional Includes | [flow-with-additional-includes](../../examples/flows/standard/flow-with-additional-includes/) | [flow-with-additional-includes-maf](../../examples/flows/standard/flow-with-additional-includes-maf/) | Demonstrates how to reference common files using additional_includes |
| Flow with Symlinks | [flow-with-symlinks](../../examples/flows/standard/flow-with-symlinks/) | [flow-with-symlinks-maf](../../examples/flows/standard/flow-with-symlinks-maf/) | Flow that uses symbolic links to reference common files across flows |
| Generate Docstring | [gen-docstring](../../examples/flows/standard/gen-docstring/) | [gen-docstring-maf](../../examples/flows/standard/gen-docstring-maf/) | Automatically generate Python docstrings for code blocks using LLM |
| Maths to Code | [maths-to-code](../../examples/flows/standard/maths-to-code/) | [maths-to-code-maf](../../examples/flows/standard/maths-to-code-maf/) | Generate executable code from math problems and execute it for answers |
| Named Entity Recognition | [named-entity-recognition](../../examples/flows/standard/named-entity-recognition/) | [named-entity-recognition-maf](../../examples/flows/standard/named-entity-recognition-maf/) | Perform NER task identifying and classifying named entities using GPT-4 |
| Question Simulation | [question-simulation](../../examples/flows/standard/question-simulation/) | [question-simulation-maf](../../examples/flows/standard/question-simulation-maf/) | Generate suggestions for next questions based on chat history context |
| Web Classification | [web-classification](../../examples/flows/standard/web-classification/) | [web-classification-maf](../../examples/flows/standard/web-classification-maf/) | Multi-class website classification from URLs using few-shot learning |

## Evaluation Flows

| Example | PF Version | MAF Version | Description |
|---|---|---|---|
| Eval Accuracy (Maths to Code) | [eval-accuracy-maths-to-code](../../examples/flows/evaluation/eval-accuracy-maths-to-code/) | [eval-accuracy-maths-to-code-maf](../../examples/flows/evaluation/eval-accuracy-maths-to-code-maf/) | Evaluates mathematical accuracy by comparing predictions to ground truth |
| Eval Basic | [eval-basic](../../examples/flows/evaluation/eval-basic/) | [eval-basic-maf](../../examples/flows/evaluation/eval-basic-maf/) | Basic evaluation flow showing how to calculate point-wise metrics |
| Eval Chat Math | [eval-chat-math](../../examples/flows/evaluation/eval-chat-math/) | [eval-chat-math-maf](../../examples/flows/evaluation/eval-chat-math-maf/) | Evaluate math question answers by comparing results numerically |
| Eval Classification Accuracy | [eval-classification-accuracy](../../examples/flows/evaluation/eval-classification-accuracy/) | [eval-classification-accuracy-maf](../../examples/flows/evaluation/eval-classification-accuracy-maf/) | Evaluate classification system performance with accuracy metrics |
| Eval Entity Match Rate | [eval-entity-match-rate](../../examples/flows/evaluation/eval-entity-match-rate/) | [eval-entity-match-rate-maf](../../examples/flows/evaluation/eval-entity-match-rate-maf/) | Evaluate how well extracted entities match expected entities |
| Eval Groundedness | [eval-groundedness](../../examples/flows/evaluation/eval-groundedness/) | [eval-groundedness-maf](../../examples/flows/evaluation/eval-groundedness-maf/) | Evaluate if answers are grounded in provided context using LLM |
| Eval Multi-Turn Metrics | [eval-multi-turn-metrics](../../examples/flows/evaluation/eval-multi-turn-metrics/) | [eval-multi-turn-metrics-maf](../../examples/flows/evaluation/eval-multi-turn-metrics-maf/) | Evaluate multi-turn conversations on quality, coherence, and engagement |
| Eval Perceived Intelligence | [eval-perceived-intelligence](../../examples/flows/evaluation/eval-perceived-intelligence/) | [eval-perceived-intelligence-maf](../../examples/flows/evaluation/eval-perceived-intelligence-maf/) | Evaluate bot perceived intelligence, creativity, and originality |
| Eval QnA Non-RAG | [eval-qna-non-rag](../../examples/flows/evaluation/eval-qna-non-rag/) | [eval-qna-non-rag-maf](../../examples/flows/evaluation/eval-qna-non-rag-maf/) | Q&A system evaluation with LLM-assisted coherence, relevance, and similarity metrics |
| Eval QnA RAG Metrics | [eval-qna-rag-metrics](../../examples/flows/evaluation/eval-qna-rag-metrics/) | [eval-qna-rag-metrics-maf](../../examples/flows/evaluation/eval-qna-rag-metrics-maf/) | RAG Q&A system evaluation with retrieval, groundedness, and relevance metrics |
| Eval Single-Turn Metrics | [eval-single-turn-metrics](../../examples/flows/evaluation/eval-single-turn-metrics/) | [eval-single-turn-metrics-maf](../../examples/flows/evaluation/eval-single-turn-metrics-maf/) | Single-turn Q&A evaluation on grounding, relevance, and answer quality |
| Eval Summarization | [eval-summarization](../../examples/flows/evaluation/eval-summarization/) | [eval-summarization-maf](../../examples/flows/evaluation/eval-summarization-maf/) | Reference-free abstractive summarization evaluation on fluency, coherence, consistency, relevance |
