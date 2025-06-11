# Release History

## 1.6.1 (2025.6.10)

- Fixed a bug that could allow for arbitrary code execution when parsing `tool_calls`
- Fixed a bug that could allow prompt injection

## 1.6.0 (2025.02.19)

### Bug fixed
- Fix for jinja2 template rendering.

## 1.5.0 (2025.01.29)

### Features Added
- Add "detail" to "Azure OpenAI GPT-4 Turbo with Vision" and "OpenAI GPT-4V" tool inputs.
- Avoid unintended parsing by role process to user flow inputs in prompt templates.
- Introduce universal contract LLM tool and combine "Azure OpenAI GPT-4 Turbo with Vision" and "OpenAI GPT-4V" tools to "LLM-Vision" tool.

### Improvements
- Dropped Python 3.8 support for security reasons.

## 1.4.0 (2024.03.26)

### Features Added
- Enable token based auth in azure openai connection for tools.
- Add "seed" to LLM and GPT-Vision tool inputs.

### Improvements
- Improve error message when LLM tool meets gpt-4-vision-preview model.

### Bugs Fixed
- Set default values to workspace triad parameters of dynamic list function to avoid misleading errors when clicking tool input.

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
