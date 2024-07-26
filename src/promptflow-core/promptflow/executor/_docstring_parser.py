from docstring_parser import parse


class DocstringParser:
    @staticmethod
    def parse_description(docstring: str):
        # TODO: Retrieve details from the function interface when the docstring lacks sufficient information.
        parsed = parse(docstring)
        params = {}
        for param in parsed.params:
            params[param.arg_name] = {"description": param.description, "type": param.type_name}

        return parsed.description or "", params
