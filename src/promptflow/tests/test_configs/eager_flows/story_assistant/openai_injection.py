import openai
from promptflow.tracing import trace


def setup_trace():
    openai.resources.beta.assistants.assistants.Assistants.create = trace(
        openai.resources.beta.assistants.assistants.Assistants.create)
    openai.resources.beta.assistants.assistants.Assistants.retrieve = trace(
        openai.resources.beta.assistants.assistants.Assistants.retrieve)
    openai.resources.beta.threads.threads.Threads.create = trace(
        openai.resources.beta.threads.threads.Threads.create)
    openai.resources.beta.threads.messages.messages.Messages.create = trace(
        openai.resources.beta.threads.messages.messages.Messages.create)
    openai.resources.beta.threads.runs.runs.Runs.create = trace(
        openai.resources.beta.threads.runs.runs.Runs.create)
    openai.resources.beta.threads.messages.messages.Messages.list = trace(
        openai.resources.beta.threads.messages.messages.Messages.list)
    openai.resources.beta.threads.runs.runs.Runs.submit_tool_outputs = trace(
        openai.resources.beta.threads.runs.runs.Runs.submit_tool_outputs)