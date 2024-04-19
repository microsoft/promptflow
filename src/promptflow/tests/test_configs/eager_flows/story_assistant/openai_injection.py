import openai
from promptflow.tracing._trace import _traced

from promptflow.tracing.contracts.trace import TraceType


def setup_trace():
    openai.resources.beta.Assistants.create = _traced(
        openai.resources.beta.Assistants.create, trace_type=TraceType.Assistant)
    openai.resources.beta.Assistants.retrieve = _traced(
        openai.resources.beta.Assistants.retrieve, trace_type=TraceType.Assistant)
    openai.resources.beta.Threads.create = _traced(
        openai.resources.beta.Threads.create)
    openai.resources.beta.threads.Messages.create = _traced(
        openai.resources.beta.threads.Messages.create)
    openai.resources.beta.threads.Runs.create = _traced(
        openai.resources.beta.threads.Runs.create)
    openai.resources.beta.threads.Messages.list = _traced(
        openai.resources.beta.threads.Messages.list)
    openai.resources.beta.threads.Runs.submit_tool_outputs = _traced(
        openai.resources.beta.threads.Runs.submit_tool_outputs)
    openai.resources.beta.threads.Runs.submit_tool_outputs_and_poll = _traced(
        openai.resources.beta.threads.Runs.submit_tool_outputs_and_poll)

    openai.resources.beta.AsyncAssistants.create = _traced(
        openai.resources.beta.AsyncAssistants.create, trace_type=TraceType.Assistant)
    openai.resources.beta.AsyncAssistants.retrieve = _traced(
        openai.resources.beta.AsyncAssistants.retrieve, trace_type=TraceType.Assistant)
    openai.resources.beta.AsyncThreads.create = _traced(
        openai.resources.beta.AsyncThreads.create)
    openai.resources.beta.threads.AsyncMessages.create = _traced(
        openai.resources.beta.threads.AsyncMessages.create)
    openai.resources.beta.threads.AsyncMessages.list = _traced(
        openai.resources.beta.threads.AsyncMessages.list)
    openai.resources.beta.threads.AsyncRuns.create = _traced(
        openai.resources.beta.threads.AsyncRuns.create)
    openai.resources.beta.threads.AsyncRuns.submit_tool_outputs = _traced(
        openai.resources.beta.threads.AsyncRuns.submit_tool_outputs)
    openai.resources.beta.threads.AsyncRuns.submit_tool_outputs_and_poll = _traced(
        openai.resources.beta.threads.AsyncRuns.submit_tool_outputs_and_poll)