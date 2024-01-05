import docutils.nodes
from docutils.core import publish_doctree


class DocstringParser:
    @staticmethod
    def parse(docstring: str):
        doctree = publish_doctree(docstring)
        description = doctree[0].astext()
        params = {}
        for field in doctree.traverse(docutils.nodes.field):
            field_name = field[0].astext()
            field_body = field[1].astext()

            if field_name.startswith("param"):
                param_name = field_name.split(" ")[1]
                if param_name not in params:
                    params[param_name] = {}
                params[param_name]["description"] = field_body
            if field_name.startswith("type"):
                param_name = field_name.split(" ")[1]
                if param_name not in params:
                    params[param_name] = {}
                params[param_name]["type"] = field_body
        return description, params
