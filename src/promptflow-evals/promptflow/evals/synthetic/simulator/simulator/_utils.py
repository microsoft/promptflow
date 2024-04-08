# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# pylint: skip-file
"""
This module contains a utility class for managing a list of JSON lines.
"""
import json


class JsonLineList(list):
    """
    A util to manage a list of JSON lines.
    """

    def to_json_lines(self):
        """
        Converts the list to a string of JSON lines.
        Each item in the list is converted to a JSON string
        and appended to the result string with a newline.

        :returns: A string of JSON lines, where each line is a JSON representation of an item in the list.
        :rtype: str
        """
        json_lines = ""
        for item in self:
            json_lines += json.dumps(item) + "\n"
        return json_lines

    def to_eval_qa_json_lines(self):
        """
        Converts the list to a string of JSON lines suitable for evaluation in a Q&A format.
        Each item in the list is expected to be a dictionary with
        'messages' key. The 'messages' value is a list of
        dictionaries, each with a 'role' key and a 'content' key.
        The 'role' value should be either 'user' or 'assistant',
        and the 'content' value should be a string.
        If a 'context' key is present in the message, its value is also included
        in the output.

        :returns: A string of JSON lines.
        :rtype: str
        """
        json_lines = ""
        for item in self:
            user_message = None
            assistant_message = None
            context = None
            for message in item["messages"]:
                if message["role"] == "user":
                    user_message = message["content"]
                elif message["role"] == "assistant":
                    assistant_message = message["content"]
                if "context" in message:
                    context = message.get("context", None)
                if user_message and assistant_message:
                    if context:
                        json_lines += (
                            json.dumps({"question": user_message, "answer": assistant_message, "context": context})
                            + "\n"
                        )
                        user_message = assistant_message = context = None
                    else:
                        json_lines += json.dumps({"question": user_message, "answer": assistant_message}) + "\n"
                        user_message = assistant_message = None

        return json_lines
