# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "plistsync"
copyright = "2025, S. Mohr & P. Spitzner"
author = "S. Mohr & P. Spitzner"

master_doc = "index"
language = "en"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration


templates_path = ["_templates"]
exclude_patterns: list[str] = []


extensions = [
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
    "sphinx_inline_tabs",
    "sphinxcontrib.typer",
    "sphinx.ext.napoleon",
    "autoapi.extension",
    # "myst_parser",
    "myst_nb",
]
autosummary_generate = True  # Turn on sphinx.ext.autosummary
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "jsonschema": ("https://python-jsonschema.readthedocs.io/en/stable", None),
}
nb_execution_mode = "off"
myst_enable_extensions = [
    "colon_fence",
    "deflist",
]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

autoapi_dirs = ["../plistsync"]
autoapi_type = "python"
autoapi_template_dir = "_templates/autoapi"
autoapi_options = [
    "members",
    "show-inheritance",
    "show-module-summary",
    "undoc-members",
    # imported-members",
]
autoapi_keep_files = True
autodoc_typehints = "signature"
autoapi_root = "api"
autoapi_ignore = ["*services*"]

html_theme = "furo"
html_static_path = ["_static"]
html_theme_options = {
    # "light_logo": "favicon-128x128-light.png",
    # "dark_logo": "favicon-128x128-dark.png",
    "light_css_variables": {
        "color-brand-primary": "#2f3992",
        "color-brand-content": "#dee2e6",
    },
    "dark_css_variables": {
        "color-brand-primary": "#2f3992",
        "color-brand-content": "#dee2e6",
    },
    # Sources for editing
    "source_view_link": "https://github.com/semohr/plistsync/blob/main/docs/{filename}",
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/semohr/plistsync",
            "html": """
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/></svg>
            """,
            "class": "",
        },
    ],
}
html_css_files = [
    "css/custom.css",
]

# html_logo = "../frontend/public/logo_flask.png"


# -- custom auto_summary() macro ---------------------------------------------


def contains(seq, item):
    """Jinja2 custom test to check existence in a container.

    Example of use:
    {% set class_methods = methods|selectattr("properties", "contains", "classmethod") %}

    Related doc: https://jinja.palletsprojects.com/en/3.1.x/api/#custom-tests
    """
    return item in seq


def prepare_jinja_env(jinja_env) -> None:
    """Add `contains` custom test to Jinja environment."""
    jinja_env.tests["contains"] = contains


autoapi_prepare_jinja_env = prepare_jinja_env

# Custom role for labels used in auto_summary() tables.
rst_prolog = """
.. role:: summarylabel
"""


# noinspection PyUnusedLocal
def autoapi_skip_members(app, what, name, obj, skip, options):
    # skip typehints and type variables
    if what == "data":
        if obj.name in ["ParamType", "TypeVar", "P", "R"]:
            skip = True
    return skip


def setup(app):
    app.connect("autoapi-skip-member", autoapi_skip_members)
    pass
