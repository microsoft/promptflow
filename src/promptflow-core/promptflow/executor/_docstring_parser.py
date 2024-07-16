import re


class DocstringParser:
    @staticmethod
    def parse_description(docstring: str):
        # Remove leading and trailing whitespaces
        docstring = "\n".join([line.strip() for line in docstring.strip().splitlines()])

        idx = DocstringParser._find_param_description_index(docstring)
        if idx == -1:
            return docstring, {}
        description = re.sub(r"\s+", " ", docstring[:idx].strip())

        param_pattern = re.compile(r":param *(\w+): *(.*?)\n", re.DOTALL)
        type_pattern = re.compile(r":type *(\w+): *(\S*)", re.DOTALL)
        params = {}
        for match in param_pattern.finditer(docstring[idx:]):
            params[match.group(1)] = {"description": match.group(2).strip(), "type": ""}
        for match in type_pattern.finditer(docstring[idx:]):
            if match.group(1) in params:
                params[match.group(1)]["type"] = match.group(2).strip()

        return description, params

    def _find_param_description_index(docstring: str):
        param_idx = docstring.find(":param ")
        type_idx = docstring.find(":type ")
        if param_idx == -1 and type_idx == -1:
            return -1
        elif param_idx == -1:
            return type_idx
        elif type_idx == -1:
            return param_idx
        else:
            return min(param_idx, type_idx)
