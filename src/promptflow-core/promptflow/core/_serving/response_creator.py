# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator

from promptflow.core._serving._errors import MultipleStreamOutputFieldsNotSupported, NotAcceptable

ACCEPT_DEFAULT = "*/*"
ACCEPT_EVENT_STREAM = "text/event-stream"
ACCEPT_JSON = {"application/json", "application/*", ACCEPT_DEFAULT}


class ResponseCreator(ABC):
    """Generates http response from flow run result."""

    def __init__(
        self,
        flow_run_result,
        accept_mimetypes,
        stream_start_callback_func=None,
        stream_end_callback_func=None,
        stream_event_callback_func=None,
        # if return the response original value, only will set to true when eager flow returns non dict value.
        response_original_value=False,
    ):
        # Fields that are with Iterator are streaming outputs.
        stream_fields = [
            k for k, v in flow_run_result.items() if isinstance(v, Iterator) or isinstance(v, AsyncIterator)
        ]
        if len(stream_fields) > 1:
            raise MultipleStreamOutputFieldsNotSupported()

        self.stream_field_name = stream_fields[0] if stream_fields else None
        self.stream_iterator = flow_run_result.pop(self.stream_field_name, None)
        self.is_async_streaming = isinstance(self.stream_iterator, AsyncIterator)
        self.non_stream_fields = flow_run_result

        # According to RFC2616, if "Accept" header is not specified,
        # then it is assumed that the client accepts all media types.
        # Set */* as the default value here.
        # https://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html
        if not accept_mimetypes:
            accept_mimetypes = {ACCEPT_DEFAULT}
        self.accept_mimetypes = accept_mimetypes
        self._on_stream_start = stream_start_callback_func
        self._on_stream_end = stream_end_callback_func
        self._on_stream_event = stream_event_callback_func
        self.response_original_value = response_original_value

    @property
    def has_stream_field(self):
        return self.stream_field_name is not None

    @property
    def accept_event_stream(self):
        """Returns True only when text/event-stream is specified explicitly.

        For other cases like */* or text/*, it will return False.
        """
        return ACCEPT_EVENT_STREAM in self.accept_mimetypes

    @property
    def accept_json(self):
        """Returns True if the Accept header includes application/json.

        It also returns True when specified with */* or application/*.
        """
        return len(ACCEPT_JSON.intersection(self.accept_mimetypes)) > 0

    def generate(self):
        start_time = time.time()
        if self._on_stream_start:
            self._on_stream_start()
        # If there are non streaming fields, yield them firstly.
        if self.non_stream_fields:
            yield format_event(self.non_stream_fields)

        # If there is stream field, read and yield data until the end.
        if self.stream_iterator is not None:
            for chunk in self.stream_iterator:
                if self._on_stream_event:
                    self._on_stream_event(chunk)
                yield format_event({self.stream_field_name: chunk})
        if self._on_stream_end:
            duration = (time.time() - start_time) * 1000
            self._on_stream_end(duration)

    async def generate_async(self):
        start_time = time.time()
        if self._on_stream_start:
            self._on_stream_start()
        # If there are non streaming fields, yield them firstly.
        if self.non_stream_fields:
            yield format_event(self.non_stream_fields)

        # If there is stream field, read and yield data until the end.
        if self.stream_iterator is not None:
            async for chunk in self.stream_iterator:
                if self._on_stream_event:
                    self._on_stream_event(chunk)
                yield format_event({self.stream_field_name: chunk})
        if self._on_stream_end:
            duration = (time.time() - start_time) * 1000
            self._on_stream_end(duration)

    @abstractmethod
    def create_text_stream_response(self):
        pass

    @abstractmethod
    def create_json_response(self):
        pass

    def create_response(self):
        if self.has_stream_field:
            if self.accept_event_stream:
                return self.create_text_stream_response()
            elif self.accept_json:
                return self.create_json_response()
            else:
                raise NotAcceptable(
                    media_type=",".join(self.accept_mimetypes),
                    supported_media_types="text/event-stream, application/json",
                )
        else:
            if self.accept_json:
                return self.create_json_response()
            else:
                raise NotAcceptable(
                    media_type=",".join(self.accept_mimetypes), supported_media_types="application/json"
                )


def format_event(data):
    return f"data: {json.dumps(data)}\n\n"
