# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import Response, jsonify

from promptflow._constants import DEFAULT_OUTPUT_NAME
from promptflow.core._serving._errors import AsyncGeneratorOutputNotSupported
from promptflow.core._serving.response_creator import ResponseCreator


class FlaskResponseCreator(ResponseCreator):
    def create_text_stream_response(self):
        if self.is_async_streaming:
            # flask doesn't support async generator output
            raise AsyncGeneratorOutputNotSupported()
        return Response(self.generate(), mimetype="text/event-stream")

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
        return jsonify(response)
