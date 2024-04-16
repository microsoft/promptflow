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
    openai.resources.beta.threads.runs.runs.Runs.submit_tool_outputs_and_poll = trace(
        openai.resources.beta.threads.runs.runs.Runs.submit_tool_outputs_and_poll)

    openai.resources.beta.assistants.assistants.AsyncAssistants.create = trace(
        openai.resources.beta.assistants.assistants.AsyncAssistants.create)
    openai.resources.beta.assistants.assistants.AsyncAssistants.retrieve = trace(
        openai.resources.beta.assistants.assistants.AsyncAssistants.retrieve)
    openai.resources.beta.threads.threads.AsyncThreads.create = trace(
        openai.resources.beta.threads.threads.AsyncThreads.create)
    openai.resources.beta.threads.messages.messages.AsyncMessages.create = trace(
        openai.resources.beta.threads.messages.messages.AsyncMessages.create)
    openai.resources.beta.threads.messages.messages.AsyncMessages.list = trace(
        openai.resources.beta.threads.messages.messages.AsyncMessages.list)
    openai.resources.beta.threads.runs.runs.AsyncRuns.create = trace(
        openai.resources.beta.threads.runs.runs.AsyncRuns.create)
    openai.resources.beta.threads.runs.runs.AsyncRuns.submit_tool_outputs = trace(
        openai.resources.beta.threads.runs.runs.AsyncRuns.submit_tool_outputs)
    openai.resources.beta.threads.runs.runs.AsyncRuns.submit_tool_outputs_and_poll = trace(
        openai.resources.beta.threads.runs.runs.AsyncRuns.submit_tool_outputs_and_poll)



