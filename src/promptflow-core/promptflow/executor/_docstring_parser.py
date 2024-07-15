import re


class DocstringParser:
    @staticmethod
    def parse_description(docstring: str):
        parts = docstring.strip().split(":param", 1)
        description = parts[0].strip()
        if len(parts) <= 1:
            return description, {}

        params_part = ":param " + parts[1].strip()
        param_pattern = re.compile(r":param *(\w+): *(.*?)\s*:type *\1: *(\S*)", re.DOTALL)
        params = {
            match.group(1): {"description": match.group(2).strip(), "type": match.group(3).strip()}
            for match in param_pattern.finditer(params_part)
        }

        return description, params
