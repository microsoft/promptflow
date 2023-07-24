from promptflow import tool
from promptflow.connections import AzureOpenAIConnection
import openai


@tool
def completion_with_stream(conn: AzureOpenAIConnection, prompt: str, deployment_name="text-ada-001"):
    generator = openai.Completion.create(
        prompt=prompt,
        engine=deployment_name,
        stream=True,
        api_key=conn.api_key,
        api_base=conn.api_base,
        api_version=conn.api_version,
        api_type=conn.api_type,
    )
    return "".join(r.choices[0].text for r in generator)
