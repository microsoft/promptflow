import docutils.nodes
from docutils.core import publish_doctree
from docutils.nodes import paragraph


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

    @staticmethod
    def parse_description(docstring: str) -> str:
        """
        Extracts the description part from a given docstring, handling multi-line descriptions
        and descriptions not starting at the first line.

        :param docstring: The complete docstring from which the description is to be extracted.
        :return: The description part of the docstring.
        """
        # Convert the docstring to a document tree
        doctree = publish_doctree(docstring)
        description = []

        # Traverse the document tree to find the first paragraph(s) before any directives or sections
        for node in doctree.traverse(paragraph):
            # Concatenate paragraph lines for the description
            description.append(node.astext())
            # Assuming the first block of paragraphs before any directive or section break is the description
            next_node = node.next_node(descend=False, siblings=True)
            if next_node and not isinstance(next_node, paragraph):
                break

        return " ".join(description)
