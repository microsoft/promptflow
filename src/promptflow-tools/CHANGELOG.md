# Release History

## 1.4.0 (Upcoming)

### Features Added
- Enable token based auth in azure openai connection for tools.
- Add "seed" to LLM and GPT-Vision tool inputs.

## 1.3.0 (2024.03.01)

### Improvements
- Disable openai built-in retry mechanism for better debuggability and real-time status updates.
- Refine the retry-after interval for openai retry error.

## 1.2.0 (2024.02.07)

### Features Added
- Support tool "Azure OpenAI GPT-4 Turbo with Vision" to auto list "deployment_name".

### Improvements
- Match the promptflow-tools setup to promptflow setup.

## 1.1.0 (2024.01.23)

### Features Added
- Use ruamel.yaml instead of pyyaml in promptflow.

## 1.0.3 (2024.01.08)

### Features Added
- Add new tool "Azure OpenAI GPT-4 Turbo with Vision".
- Support "response_format" for azure openai chat api in LLM tool.

## 1.0.1 (2023.12.13)

### Features Added
- Support "response_format" for openai chat api in LLM tool.
- Add "allow_manual_entry" for embedding tool.

### Improvements
- Handle all OpenSource\HuggingFace Models with the same MIR request format in 'Open Model LLM' tool.

## 1.0.0 (2023.11.30)

### Features Added
- Support openai 1.x in promptflow-tools.
- Add new tool "OpenAI GPT-4V".
