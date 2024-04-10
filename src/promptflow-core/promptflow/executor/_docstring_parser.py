import docutils.nodes
from docutils.core import publish_doctree


class DocstringParser:
    @staticmethod
    def parse_description(docstring: str):
        # Parse the descriptions of method and parameters from the docstring at best, allowing for some flexibility
        doctree = publish_doctree(docstring)
        # Initialize variables
        description_lines = []
        param_descriptions = {}

        # Use flags to help determine the correct processing logic
        found_param_or_type = False

        # Traverse the document tree to process nodes
        for node in doctree.traverse():
            if isinstance(node, docutils.nodes.field):
                found_param_or_type = True  # Mark when we encounter parameter or type fields
                field_name = node.children[0].astext().strip()
                field_body = node.children[1].astext().strip()

                # Handle ":param" and ":type" annotations
                if field_name.startswith("param"):
                    param_name = field_name.split("param")[1].strip()
                    param_descriptions.setdefault(param_name, {})["description"] = field_body

            # Process the first paragraph only if we haven't found any parameter or type fields yet
            elif isinstance(node, docutils.nodes.paragraph) and not found_param_or_type:
                description_lines.append(node.astext().strip())

        # Join collected description lines with a space
        description = " ".join(description_lines).strip()

        return description, param_descriptions
