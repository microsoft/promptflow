# -- Path setup --------------------------------------------------------------
import sys

# -- Project information -----------------------------------------------------

project = 'Prompt flow'
copyright = '2023, Microsoft'
author = 'Microsoft'

sys.path.append(".")
from gallery_directive import GalleryDirective  # noqa: E402


# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.todo",
    "sphinxext.rediraffe",
    "sphinx_design",
    "sphinx_copybutton",
    "matplotlib.sphinxext.plot_directive",
    "sphinx_togglebutton",
    'myst_parser',
    "sphinx.builders.linkcheck",
]

# -- Internationalization ------------------------------------------------
# specifying the natural language populates some key tags
language = "en"

# spcify charset as utf-8 to accept chinese punctuation
charset_type = "utf-8"

autosummary_generate = True

# Add any paths that contain templates here, relative to this directory.
# templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = [
    "_build", "Thumbs.db", ".DS_Store", "**.ipynb_checkpoints",
    "**.py", "**.yml", "**.ipynb", "**.sh", "**.zip", "**.skip"
]

# Options for the linkcheck builder
linkcheck_ignore = [
    r"https://platform\.openai\.com/",
    # These are used in card links, for example 'xx.html', .md can't be resolved.
    r"^(?!https?)",
    "deploy-using-docker.html",
    "deploy-using-kubernetes.html",
]

linkcheck_exclude_documents = ["contributing"]

# -- Extension options -------------------------------------------------------

# This allows us to use ::: to denote directives, useful for admonitions
myst_enable_extensions = ["colon_fence", "substitution"]

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "pydata_sphinx_theme"
html_logo = "_static/logo.svg"
html_favicon = "_static/logo32.ico"
html_sourcelink_suffix = ""
html_show_sourcelink = False

# Define the json_url for our version switcher.

html_theme_options = {
    "github_url": "https://github.com/microsoft/promptflow",
    "header_links_before_dropdown": 6,
    "icon_links": [
        {
            "name": "PyPI",
            "url": "https://pypi.org/project/promptflow/",
            "icon": "fa-solid fa-box",
        },
    ],
    "logo": {
        "text": "Prompt flow",
        "alt_text": "Prompt flow",
    },
    "use_edit_page_button": True,
    "show_toc_level": 1,
    "navbar_align": "left",  # [left, content, right] For testing that the navbar items align properly
    "navbar_center": ["navbar-nav"],
    # "announcement": "Test our announcement here.",
    "show_nav_level": 1,
}

html_sidebars = {
    # "quick_start/README.md": ['localtoc.html', 'relations.html', 'searchbox.html'],
    # "examples/persistent-search-field": ["search-field"],
    # Blog sidebars
    # ref: https://ablog.readthedocs.io/manual/ablog-configuration-options/#blog-sidebars
    "features": ['localtoc.html', 'relations.html', 'searchbox.html'],
    # "tutorials": ['localtoc.html', 'relations.html', 'searchbox.html'],
}

html_context = {
    "default_mode": "light",
    "github_user": "",
    "github_repo": "microsoft/promptflow",
    "github_version": "main",
    "doc_path": "docs",
}

rediraffe_redirects = {
}


# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_js_files = ['custom.js']
todo_include_todos = True


# myst reference config
myst_heading_anchors = 5



def setup(app):
    # Add the gallery directive
    app.add_directive("gallery-grid", GalleryDirective)
