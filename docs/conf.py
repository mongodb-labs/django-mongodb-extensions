# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

from __future__ import annotations

import sys
from importlib.metadata import version as _version
from pathlib import Path

sys.path.append(str((Path(__file__).parent / "_ext").resolve()))

project = "Django MongoDB Extensions"
copyright = "2025, The MongoDB Python Team"
author = "The MongoDB Python Team"
release = _version("django_mongodb_extensions")

add_module_names = False
toc_object_entries = False

extensions = [
    "djangodocs",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
]

exclude_patterns = ["_build"]

intersphinx_mapping = {
    "django": (
        "https://docs.djangoproject.com/en/stable/",
        "https://docs.djangoproject.com/en/stable/_objects/",
    ),
    "python": ("https://docs.python.org/3/", None),
}

html_theme = "furo"

copybutton_prompt_text = r">>> |\.\.\. |\$ "
copybutton_prompt_is_regexp = True
