import asyncio
import contextvars
import functools
import typing
from typing import Union

from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from starlette.concurrency import T, _next, _StopIteration
from starlette.responses import ContentStream


class PromptflowStreamingResponse(StreamingResponse):
    """StreamingResponse with support for synchronous iterators.

    This class is to fix the opentelemetry issue in streaming case where the span creation and close
    runs in different threads with different context.
    For more details, please refer to: https://github.com/open-telemetry/opentelemetry-python/issues/2606
    """

    def __init__(
        self,
        content: ContentStream,
        status_code: int = 200,
        headers: Union[typing.Mapping[str, str], None] = None,
        media_type: Union[str, None] = None,
        background: Union[BackgroundTask, None] = None,
    ) -> None:
        self.sync_running = False
        self.connection_break = False
        if not isinstance(content, typing.AsyncIterable):
            self.semaphore = asyncio.Semaphore(0)
            self.sync_content = content
            self.sync_running = True
            content = iterate_in_threadpool(content)
        super().__init__(content, status_code, headers, media_type, background)


async def iterate_in_threadpool(
    iterator: typing.Iterable[T],
) -> typing.AsyncIterator[T]:
    as_iterator = iter(iterator)
    ctx = contextvars.copy_context()
    func_call = functools.partial(ctx.run, _next, as_iterator)
    while True:
        try:
            yield await asyncio.get_running_loop().run_in_executor(None, func_call)
        except _StopIteration:
            break
