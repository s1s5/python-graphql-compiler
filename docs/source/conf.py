# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

from __future__ import annotations

import os
import sys

on_rtd = os.environ.get("READTHEDOCS") == "True"

docs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
project_dir = os.path.abspath(os.path.join(docs_dir, ".."))
package_dir = os.path.abspath(os.path.join(project_dir, "python_graphql_compiler"))

sys.path.insert(0, project_dir)

import python_graphql_compiler  # noqa: E402

# -- Project information -----------------------------------------------------

# General information about the project.
project = "Python Graphql Compiler"
author = python_graphql_compiler.__author__
copyright = "2021, " + python_graphql_compiler.__author__

# The version info for the project you"re documenting, acts as replacement
# for |version| and |release|, also used in various other places throughout
# the built documents.
#
# The short X.Y version.
version = python_graphql_compiler.__version__
# The full version, including alpha/beta/rc tags.
release = python_graphql_compiler.__version__


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named "sphinx.ext.*") or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.coverage",
    "sphinx.ext.doctest",
    "sphinx.ext.githubpages",
    "sphinx.ext.ifconfig",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = None

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns: list[str] = []

# Warnings to suppress
suppress_warnings = ["autosectionlabel.*"]

# -- Autoapi configuration ---------------------------------------------------

extensions.append("autoapi.extension")

autoapi_type = "python"
autoapi_dirs = [package_dir]
autoapi_keep_files = False

# -- Nbsphinx configuration --------------------------------------------------

if not on_rtd:
    extensions.append("nbsphinx")

html_sourcelink_suffix = ""

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "alabaster"
pygments_style = "sphinx"

# Theme options are theme-specific and customize the look and feel of a
# theme further.  For a list of options available for each theme, see the
# documentation.
#
html_theme_options = {
    "description": "Python graphql compiler",  # noqa: E501
    "fixed_sidebar": "true",
    "github_user": "s1s5",
    "github_repo": "python-graphql-compiler",
    "github_banner": "true",
    "github_button": "true",
    "github_type": "star",
    "font_family": "'Noto Serif KR', Georgia, 'Times New Roman', Times, serif",
    "head_font_family": "'Noto Serif KR', Georgia, 'Times New Roman', Times, serif",
    "code_font_family": "'D2Coding', 'Consolas', 'Menlo', 'DejaVu Sans Mono', 'Bitstream Vera Sans Mono', monospace",
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# Edit this css file to override some existing styles.
html_css_files = [
    "css/style.css",
]
