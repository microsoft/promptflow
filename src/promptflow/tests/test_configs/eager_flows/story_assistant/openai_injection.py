import openai
from promptflow.tracing import trace


def setup_trace():
    openai.resources.beta.Assistants.create = trace(
        openai.resources.beta.Assistants.create)
    openai.resources.beta.Assistants.retrieve = trace(
        openai.resources.beta.Assistants.retrieve)
    openai.resources.beta.Threads.create = trace(
        openai.resources.beta.Threads.create)
    openai.resources.beta.threads.Messages.create = trace(
        openai.resources.beta.threads.Messages.create)
    openai.resources.beta.threads.Runs.create = trace(
        openai.resources.beta.threads.Runs.create)
    openai.resources.beta.threads.Messages.list = trace(
        openai.resources.beta.threads.Messages.list)
    openai.resources.beta.threads.Runs.submit_tool_outputs = trace(
        openai.resources.beta.threads.Runs.submit_tool_outputs)
    openai.resources.beta.threads.Runs.submit_tool_outputs_and_poll = trace(
        openai.resources.beta.threads.Runs.submit_tool_outputs_and_poll)

    openai.resources.beta.AsyncAssistants.create = trace(
        openai.resources.beta.AsyncAssistants.create)
    openai.resources.beta.AsyncAssistants.retrieve = trace(
        openai.resources.beta.AsyncAssistants.retrieve)
    openai.resources.beta.AsyncThreads.create = trace(
        openai.resources.beta.AsyncThreads.create)
    openai.resources.beta.threads.AsyncMessages.create = trace(
        openai.resources.beta.threads.AsyncMessages.create)
    openai.resources.beta.threads.AsyncMessages.list = trace(
        openai.resources.beta.threads.AsyncMessages.list)
    openai.resources.beta.threads.AsyncRuns.create = trace(
        openai.resources.beta.threads.AsyncRuns.create)
    openai.resources.beta.threads.AsyncRuns.submit_tool_outputs = trace(
        openai.resources.beta.threads.AsyncRuns.submit_tool_outputs)
    openai.resources.beta.threads.AsyncRuns.submit_tool_outputs_and_poll = trace(
        openai.resources.beta.threads.AsyncRuns.submit_tool_outputs_and_poll)