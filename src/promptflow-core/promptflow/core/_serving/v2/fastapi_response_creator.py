# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from fastapi.responses import JSONResponse

from promptflow._constants import DEFAULT_OUTPUT_NAME
from promptflow.core._serving.response_creator import ResponseCreator

from .pf_streaming_response import PromptflowStreamingResponse


class FastapiResponseCreator(ResponseCreator):
    def create_text_stream_response(self):
        if self.is_async_streaming:
            content = self.generate_async()
        else:
            content = self.generate()
        return PromptflowStreamingResponse(content=content, media_type="text/event-stream")

    def create_json_response(self):
        # If there is stream field, iterate over it and get the merged result.
        if self.stream_iterator is not None:
            merged_text = "".join(self.stream_iterator)
            self.non_stream_fields[self.stream_field_name] = merged_text
        if self.response_original_value:
            response = self.non_stream_fields.get(DEFAULT_OUTPUT_NAME)
        else:
            response = self.non_stream_fields
        # TODO: check non json dumpable results
        return JSONResponse(response)
