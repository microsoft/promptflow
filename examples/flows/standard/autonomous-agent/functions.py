from promptflow.core import tool


@tool
def functions_format() -> list:
    functions = [
        {
            "name": "search",
            "description": """The action will search this entity name on Wikipedia and returns the first {count}
            sentences if it exists. If not, it will return some related entities to search next.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Entity name which is used for Wikipedia search.",
                    },
                    "count": {
                        "type": "integer",
                        "default": 10,
                        "description": "Returned sentences count if entity name exists Wikipedia.",
                    },
                },
                "required": ["entity"],
            },
        },
        {
            "name": "python",
            "description": """A Python shell. Use this to execute python commands. Input should be a valid python
            command and you should print result with `print(...)` to see the output.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command you want to execute in python",
                    }
                  },
                "required": ["command"]
            },
        },
        {
            "name": "finish",
            "description": """use this to signal that you have finished all your goals and remember show your
            results""",
            "parameters": {
                "type": "object",
                "properties": {
                    "response": {
                        "type": "string",
                        "description": "final response to let people know you have finished your goals and remember "
                                       "show your results",
                    },
                },
                "required": ["response"],
             },
        },
      ]
    return functions
