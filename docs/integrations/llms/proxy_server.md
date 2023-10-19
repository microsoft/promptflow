## Use Anthropic,Huggingface,Palm,Ollama, etc.[Full List](https://docs.litellm.ai/docs/providers)

### Create OpenAI-proxy
We'll use [LiteLLM](https://docs.litellm.ai/docs/) to create an OpenAI-compatible endpoint, that translates OpenAI calls to any of the [supported providers](https://docs.litellm.ai/docs/providers).


Example to use a local CodeLLama model from Ollama.ai with PromptFlow: 

Let's spin up a proxy server to route any OpenAI call from PromptFlow to Ollama/CodeLlama

```python
pip install litellm
```
```python
$ litellm --model ollama/codellama

#INFO: Ollama running on http://0.0.0.0:8000
```

[Docs](https://docs.litellm.ai/docs/proxy_server)

### Update PromptFlow

```python
pf connection create --file ./my_chatbot/azure_openai.yaml --set api_key="my-fake-key" api_base=http://0.0.0.0:8000 --name open_ai_connection
```