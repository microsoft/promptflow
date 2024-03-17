from pathlib import Path
from typing import TypedDict

from openai import AzureOpenAI

from promptflow.tracing import trace
import os

BASE_DIR = Path(__file__).absolute().parent


class Result(TypedDict):
    output: str

@trace
def flow_entry(question: str = "Can you make a joke?") -> Result:
    """Flow entry function."""
    
    deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "text-davinci-003")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2023-07-01-preview")

    if "AZURE_OPENAI_API_KEY" not in os.environ:
        raise Exception("Please specify environment variables: AZURE_OPENAI_API_KEY")
    
    if "AZURE_OPENAI_ENDPOINT" not in os.environ:
        raise Exception("Please specify environment variables: AZURE_OPENAI_ENDPOINT")
    
    # gets the API Key from environment variable AZURE_OPENAI_API_KEY
    client = AzureOpenAI(
        api_version=api_version,
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    )
    
    response = client.chat.completions.create(
        model=deployment_name,
        messages=[
            {"role": "system", "content": "Assistant is a large language model trained by OpenAI."},
            {"role": "user", "content": question}
        ],
        max_tokens=800
    )
    return Result(output=response.choices[0].message.content)

if __name__ == "__main__":
    from promptflow.tracing import start_trace

    start_trace()

    result = flow_entry("Who's the best NBA player?")
    print(result)
