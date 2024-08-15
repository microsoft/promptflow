# promptflow-core package

## v1.15.0 (2024.08.15)

### Bugs fixed
- Fixed openai error handler not functioning for `AsyncPrompty`.

## v1.14.0 (2024.07.25)
### Improvements
- Remove dependency on docutils package.

## v1.13.0 (2024.06.28)

### Bug fixed
- Fix `AsyncFlow.load(source="path/to/prompty")` does not return a AsyncPrompty object.

## v1.12.0 (2024.06.11)

### Bugs fixed
- Fix ChatUI can't work in docker container when running image build with `pf flow build`.
- Fix [#3355](https://github.com/microsoft/promptflow/issues/3355) that IndexError is raised when generator is used in a flow and the flow is called inside another flow.

## v1.11.0 (2024.05.17)

### Features Added
- Support modifying the promptflow logger format through environment variables, reach [here](https://microsoft.github.io/promptflow/how-to-guides/faq.html#set-logging-format) for more details.
- Support async generator in flex flow.

## v1.10.0 (2024.04.26)

### Features Added
- Add prompty feature to simplify the development of prompt templates for customers, reach [here](https://microsoft.github.io/promptflow/how-to-guides/develop-a-prompty/index.html) for more details.

### Others
- Add fastapi serving engine support.

## v1.9.0 (2024.04.17)

### Others
- Connection default api version changed:
  - AzureOpenAIConnection: 2023-07-01-preview -> 2024-02-01
  - CognitiveSearchConnection: 2023-07-01-preview -> 2023-11-01
