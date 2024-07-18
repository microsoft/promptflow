from docstring_parser import parse


class DocstringParser:
    @staticmethod
    def parse_description(docstring: str):
        parsed = parse(docstring)

        description = (
            (short + " " + long if (long := parsed.long_description) is not None else short)
            if (short := parsed.short_description) is not None
            else None
        )

        params = {}
        for param in parsed.params:
            params[param.arg_name] = {"description": param.description, "type": param.type_name}

        return description, params
