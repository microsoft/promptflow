"""A directive to generate a gallery of images from structured data.
Generating a gallery of images that are all the same size is a common
pattern in documentation, and this can be cumbersome if the gallery is
generated programmatically. This directive wraps this particular use-case
in a helper-directive to generate it with a single YAML configuration file.
It currently exists for maintainers of the pydata-sphinx-theme,
but might be abstracted into a standalone package if it proves useful.
"""
from yaml import safe_load
from typing import List
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.util.docutils import SphinxDirective
from sphinx.util import logging

logger = logging.getLogger(__name__)


TEMPLATE_GRID = """
`````{{grid}} {grid_columns}
{container_options}
{content}
`````
"""

GRID_CARD = """
````{{grid-item-card}} {title}
{card_options}
{content}
````
"""


class GalleryDirective(SphinxDirective):
    """A directive to show a gallery of images and links in a grid."""

    name = "gallery-grid"
    has_content = True
    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True
    option_spec = {
        # A class to be added to the resulting container
        "grid-columns": directives.unchanged,
        "class-container": directives.unchanged,
        "class-card": directives.unchanged,
    }

    def run(self) -> List[nodes.Node]:  # noqa: C901
        if self.arguments:
            # If an argument is given, assume it's a path to a YAML file
            # Parse it and load it into the directive content
            path_data_rel = Path(self.arguments[0])
            path_doc, _ = self.get_source_info()
            path_doc = Path(path_doc).parent
            path_data = (path_doc / path_data_rel).resolve()
            if not path_data.exists():
                logger.warn(f"Could not find grid data at {path_data}.")
                nodes.text("No grid data found at {path_data}.")
                return
            yaml_string = path_data.read_text()
        else:
            yaml_string = "\n".join(self.content)

        # Read in YAML so we can generate the gallery
        grid_data = safe_load(yaml_string)

        grid_items = []
        for item in grid_data:
            # Grid card parameters
            options = {}
            if "website" in item:
                options["link"] = item["website"]

            if "class-card" in self.options:
                options["class-card"] = self.options["class-card"]

            if "img-background" in item:
                options["img-background"] = item["img-background"]

            if "img-top" in item:
                options["img-top"] = item["img-top"]

            if "img-bottom" in item:
                options["img-bottom"] = item["img-bottom"]

            options_str = "\n".join(f":{k}: {v}" for k, v in options.items()) + "\n\n"

            # Grid card content
            content_str = ""
            if "header" in item:
                content_str += f"{item['header']}\n\n^^^\n\n"

            if "image" in item:
                content_str += f"![Gallery image]({item['image']})\n\n"

            if "content" in item:
                content_str += f"{item['content']}\n\n"

            if "footer" in item:
                content_str += f"+++\n\n{item['footer']}\n\n"

            title = item.get("title", "")
            content_str += "\n"
            grid_items.append(
                GRID_CARD.format(
                    card_options=options_str, content=content_str, title=title
                )
            )

        # Parse the template with Sphinx Design to create an output
        container = nodes.container()
        # Prep the options for the template grid
        container_options = {"gutter": 2, "class-container": "gallery-directive"}
        if "class-container" in self.options:
            container_options[
                "class-container"
            ] += f' {self.options["class-container"]}'
        container_options_str = "\n".join(
            f":{k}: {v}" for k, v in container_options.items()
        )

        # Create the directive string for the grid
        grid_directive = TEMPLATE_GRID.format(
            grid_columns=self.options.get("grid-columns", "1 2 3 4"),
            container_options=container_options_str,
            content="\n".join(grid_items),
        )
        # Parse content as a directive so Sphinx Design processes it
        self.state.nested_parse([grid_directive], 0, container)
        # Sphinx Design outputs a container too, so just use that
        container = container.children[0]

        # Add extra classes
        if self.options.get("container-class", []):
            container.attributes["classes"] += self.options.get("class", [])
        return [container]
