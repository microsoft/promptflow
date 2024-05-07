# Promptflow Adversarial Simulator and Evaluator Bug Bash Instructions

## Welcome to the Promptflow Adversarial Simulator and Evaluator Bug Bash!

### Prerequisites
- Azure Open AI Endpoint
- Open AI Model Deployment that supports `chat completion`
- Azure AI Project
  - Needed for content safety metrics.
  - Project should be in one of the following reason if you would like to try out content safety evaluators
    - `East US 2`
    - `Sweden Central`
    - `France Central`
    - `UK South`
  - For local to remote tracking

### Clone the repo
```bash
git clone https://github.com/microsoft/promptflow.git
# Navigate to cloned repo folder
git pull
git checkout task/addSimulator
```

### Installation Instructions:

1. Create a **virtual environment of you choice**.
    To create one using conda, run the following command:
    ```bash
    conda create -n promptflow-evals-bug-bash python=3.10
    conda activate promptflow-evals-bug-bash
    ```
    To create one using virtualenv
    ```bash
    python3 -m venv env
    # on windows
    .\env\Scripts\activate
    # on linux based
    source ./env/bin/activate
    ```
2. Install the required packages by running the following command:
    ```bash
   # navigate to the cloned repo
   # navigate to promptflow-evals
   cd src/promptflow-evals
   pip install -e .
    ```

### Report Bugs

Please use the following template to report bugs : [**Bug Template**](https://aka.ms/aicodefirst/createbug)

### Sample Scripts

Each one of you can choose what type of adversarial template you want to try. Here's the list of available templates:

- [ ] `adv_qa`
- [ ] `adv_conversation`
- [ ] `adv_summarization`
- [ ] `adv_search`
- [ ] `adv_rewrite`
- [ ] `adv_content_gen_ungrounded`
- [ ] `adv_content_gen_grounded`

Create a new python file with any name you want. Paste the following snippet:

```python
from promptflow.evals.synthetic import AdversarialSimulator
from azure.identity import DefaultAzureCredential
from typing import Any, Dict, List, Optional
import asyncio

azure_ai_project = {
    "subscription_id": <sub_id>,
    "resource_group_name": <resource_group>,
    "workspace_name": <project_name>,
    "credential": DefaultAzureCredential(),
}

async def callback(
    messages: List[Dict],
    stream: bool = False,
    session_state: Any = None,
) -> dict:
    question = messages["messages"][0]["content"]
    context = None
    if 'file_content' in messages["template_parameters"]:
        question += messages["template_parameters"]['file_content']

    # the next few lines explains how to use the AsyncAzureOpenAI's chat.completions
    # to respond to the simulator. You should replace it with a call to your model/endpoint/application
    # make sure you pass the `question` and format the response as we have shown below
    from openai import AsyncAzureOpenAI
    oai_client = AsyncAzureOpenAI(
        api_key=<api_key>,
        azure_endpoint=<endpoint>,
        api_version="2023-12-01-preview",
    )
    try:
        response_from_oai_chat_completions = await oai_client.chat.completions.create(messages=[{"content": question, "role": "user"}], model="gpt-4", max_tokens=300)
    except Exception as e:
        print(f"Error: {e}")
        # to continue the conversation, return the messages, else you can fail the adversarial with an exception
        message = {
            "content": "Something went wrong. Check the exception e for more details.",
            "role": "assistant",
            "context": None,
        }
        messages["messages"].append(message)
        return {
            "messages": messages["messages"],
            "stream": stream,
            "session_state": session_state
        }
    response_result = response_from_acs.choices[0].message.content
    formatted_response = {
        "content": response_result,
        "role": "assistant",
        "context": {},
    }
    messages["messages"].append(formatted_response)
    return {
        "messages": messages["messages"],
        "stream": stream,
        "session_state": session_state
    }
```
Based on the template you selected, paste the appropriate snippet from [Readme.md](https://github.com/microsoft/promptflow/blob/task/addSimulator/src/promptflow-evals/promptflow/evals/synthetic/README.md) into your python script which has the `callback`

### Running evaluations
Check [this section](https://github.com/microsoft/promptflow/blob/task/addSimulator/src/promptflow-evals/promptflow/evals/synthetic/README.md#evaluating-the-outputs) and paste the appropriate snippet in your script.

Run your script!
