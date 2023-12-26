from jinja2 import Template
from promptflow import PFClient, flow
from promptflow.tools.aoai import chat

from promptflow.contracts.types import PromptTemplate

@flow
def flow_entry(prompt: str):
    client = PFClient()
    connection = client.connections.get(name="open_ai_connection", with_secrets=True)
    with open("hello.jinja2") as f:
        template = Template(f.read())
        prompt = template.render(text=prompt)
    results = {}
    for max_tokens in [128, 256]:
        results[max_tokens] = chat(prompt=PromptTemplate(prompt), connection=connection, max_tokens=max_tokens, deployment_name="gpt-35-turbo")
    return {"val1": results[128], "val2": results[256]}

if __name__ == "__main__":
    flow_entry(prompt="Hello, world!")
