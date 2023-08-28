# Autonomous Agent

This is a flow showcasing how to construct a AutoGPT agent with promptflow to autonomously figures out how to apply the given functions 
to solve the goal, which is film trivia that provides accurate and up-to-date information about movies, directors, 
actors, and more in this sample.

It involves inferring next executed function and user intent with LLM, and then use the function to generate 
observation. The observation above will be used as augmented prompt which is the input of next LLM inferring loop 
until the inferred function is the signal that you have finished all your objectives. The functions set used in the 
flow contains Wikipedia search function that can search the web to find answer about current events and PythonREPL 
python function that can run python code in a REPL.

For the sample input about movie introduction, the AutoGPT usually runs 4 rounds to finish the task. The first round 
is searching for the movie name, the second round is searching for the movie director, the third round is calculating 
director age, and the last round is outputting finishing signal. It takes 30s~40s to finish the task, but may take 
longer time if you use "gpt-3.5" or encounter Azure OpenAI rate limit. You could use "gpt-4" or go to 
https://aka.ms/oai/quotaincrease if you would like to further increase the default rate limit.

Note: This is just a sample introducing how to use promptflow to build a simple AutoGPT. You can go to 
https://github.com/Significant-Gravitas/Auto-GPT to get more concepts about AutoGPT.

## What you will learn

In this flow, you will learn
- how to use prompt tool.
- how to compose an AutoGPT flow using functions.

## Prerequisites

Install prompt-flow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Getting Started

### 1 Create Azure OpenAI or OpenAI connection
```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```
Note that you need to use "2023-07-01-preview" as Azure OpenAI connection API version when using function calling.
See <a href='https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/function-calling' target='_blank'>How to use function calling with Azure OpenAI Service</a> for more details.

### 2. Configure the flow with your connection
`flow.dag.yaml` is already configured with connection named `open_ai_connection`. It is recommended to use "gpt-4" model for stable performance. Using "gpt-3.5-turbo" may lead to the model getting stuck in the agent inner loop due to its suboptimal and unstable performance.

### 3. Test flow with single line data

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .
```

### 4. Run with multi-line data

```bash
# create run using command line args
pf run create --flow . --data ./data.jsonl --stream
```

## Disclaimer
LLM systems are susceptible to prompt injection, and you can gain a deeper understanding of this issue in the [technical blog](https://developer.nvidia.com/blog/securing-llm-systems-against-prompt-injection/). As an illustration, the PythonREPL function might execute harmful code if provided with a malicious prompt within the provided sample. Furthermore, we cannot guarantee that implementing AST validations solely within the PythonREPL function will reliably elevate the sample's security to an enterprise level. We kindly remind you to refrain from utilizing this in a production environment.