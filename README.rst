=======================
Python Graphql Compiler
=======================

.. container::

    .. image:: https://img.shields.io/pypi/v/python_graphql_compiler.svg
            :target: https://pypi.python.org/pypi/python_graphql_compiler
            :alt: PyPI Version

    .. image:: https://img.shields.io/pypi/pyversions/python_graphql_compiler.svg
            :target: https://pypi.python.org/pypi/python_graphql_compiler/
            :alt: PyPI Python Versions

    .. image:: https://img.shields.io/pypi/status/python_graphql_compiler.svg
            :target: https://pypi.python.org/pypi/python_graphql_compiler/
            :alt: PyPI Status

    .. badges from below are commendted out

    .. .. image:: https://img.shields.io/pypi/dm/python_graphql_compiler.svg
            :target: https://pypi.python.org/pypi/python_graphql_compiler/
            :alt: PyPI Monthly Donwloads

.. container::

    .. image:: https://img.shields.io/github/workflow/status/s1s5/python-graphql-compiler/CI/master
            :target: https://github.com/s1s5/python-graphql-compiler/actions/workflows/ci.yml
            :alt: CI Build Status
    .. .. image:: https://github.com/s1s5/python-graphql-compiler/actions/workflows/ci.yml/badge.svg?branch=master

    .. image:: https://img.shields.io/github/workflow/status/s1s5/python-graphql-compiler/Documentation/master?label=docs
            :target: https://s1s5.github.io/python-graphql-compiler/
            :alt: Documentation Build Status
    .. .. image:: https://github.com/s1s5/python-graphql-compiler/actions/workflows/documentation.yml/badge.svg?branch=master

    .. image:: https://img.shields.io/codecov/c/github/s1s5/python-graphql-compiler.svg
            :target: https://codecov.io/gh/s1s5/python-graphql-compiler
            :alt: Codecov Coverage
    .. .. image:: https://codecov.io/gh/s1s5/python-graphql-compiler/branch/master/graph/badge.svg

    .. image:: https://img.shields.io/requires/github/s1s5/python-graphql-compiler/master.svg
            :target: https://requires.io/github/s1s5/python-graphql-compiler/requirements/?branch=master
            :alt: Requires.io Requirements Status
    .. .. image:: https://requires.io/github/s1s5/python-graphql-compiler/requirements.svg?branch=master

    .. badges from below are commendted out

    .. .. image:: https://img.shields.io/travis/s1s5/python-graphql-compiler.svg
            :target: https://travis-ci.com/s1s5/python-graphql-compiler
            :alt: Travis CI Build Status
    .. .. image:: https://travis-ci.com/s1s5/python-graphql-compiler.svg?branch=master

    .. .. image:: https://img.shields.io/readthedocs/python-graphql-compiler/latest.svg
            :target: https://python-graphql-compiler.readthedocs.io/en/latest/?badge=latest
            :alt: ReadTheDocs Documentation Build Status
    .. .. image:: https://readthedocs.org/projects/python-graphql-compiler/badge/?version=latest

    .. .. image:: https://pyup.io/repos/github/s1s5/python-graphql-compiler/shield.svg
            :target: https://pyup.io/repos/github/s1s5/python-graphql-compiler/
            :alt: PyUp Updates

.. container::

    .. image:: https://img.shields.io/pypi/l/python_graphql_compiler.svg
            :target: https://github.com/s1s5/python-graphql-compiler/blob/master/LICENSE
            :alt: PyPI License

    .. image:: https://app.fossa.com/api/projects/git%2Bgithub.com%2Fs1s5%2Fpython-graphql-compiler.svg?type=shield
            :target: https://app.fossa.com/projects/git%2Bgithub.com%2Fs1s5%2Fpython-graphql-compiler?ref=badge_shield
            :alt: FOSSA Status

.. container::

    .. image:: https://badges.gitter.im/s1s5/python-graphql-compiler.svg
            :target: https://gitter.im/python-graphql-compiler/community
            :alt: Gitter Chat
    .. .. image:: https://img.shields.io/gitter/room/s1s5/python-graphql-compiler.svg

    .. image:: https://img.shields.io/badge/code%20style-black-000000.svg
            :target: https://github.com/psf/black
            :alt: Code Style: Black

Python graphql compiler

* Free software: `MIT License`_
* Documentation: https://python-graphql-compiler.readthedocs.io.

.. _`MIT License`: https://github.com/s1s5/python-graphql-compiler/blob/master/LICENSE

Features
--------
Generate type information from graphql queries.

.. code-block:: text

    query GetObject($id: ID!) {
      droid(id: $id) {
        __typename
        id name appearsIn primaryFunction
      }
    }

.. code-block:: python

    Episode = typing.Literal["NEWHOPE", "EMPIRE", "JEDI"]


    @dataclass
    class GetObject__droid:
        _typename: typing.Literal["Droid"]
        appearsIn: typing.List[Episode]
        id: str
        name: str
        primaryFunction: str
        def __init__(self, _typename, appearsIn, id, name, primaryFunction):
            self._typename = _typename
            self.appearsIn = appearsIn
            self.id = id
            self.name = name
            self.primaryFunction = primaryFunction


    @dataclass
    class GetObjectResponse:
        droid: GetObject__droid
        def __init__(self, droid):
            self.droid = GetObject__droid(**demangle(droid, ['__typename']))
    
    
    _GetObjectInput__required = typing.TypedDict("_GetObjectInput__required", {"id": str})
    _GetObjectInput__not_required = typing.TypedDict("_GetObjectInput__not_required", {}, total=False)
    
    
    class _GetObjectInput(_GetObjectInput__required, _GetObjectInput__not_required):
        pass
    
    
    def _GetObjectInput__serialize(data):
        ret = copy.copy(data)
        return ret
    
    
    class GetObject(utils.Client[_GetObjectInput, GetObjectResponse]):
        _query = inspect.cleandoc('''
            query GetObject($id: ID!) {
              droid(id: $id) {
                __typename
                id name appearsIn primaryFunction
              }
            }
        ''')
        Input: typing.TypeAlias = _GetObjectInput
        Response: typing.TypeAlias = GetObjectResponse
    
        @classmethod
        def serialize(cls, data: _GetObjectInput):
            return {
                "operation_name": "GetObject",
                "query": cls._query,
                "variables": _GetObjectInput__serialize(data),
            }
    
        @classmethod
        def deserialize(cls, data):
            return cls.Response(**data)

Usage
-------
.. code-block:: console

    $ python -m python_graphql_compiler --help
    Usage: python -m python_graphql_compiler [OPTIONS]
    
    Options:
      -s, --schema TEXT  the graphql schemas storage path or url
      -q, --query TEXT   path where query file or directory all queries files are
                         stored
      -c, --config TEXT  path where config yaml file
      --version          Show the version and exit.
      --help             Show this message and exit.

    $ python -m python_graphql_compiler -s baseschema.graphql -s schema.grpahql -q query0.graphql -q query1.graphql -c config.yml


config
-------
.. code-block:: yaml
    scalar_map:
      DateTime:
          import: "import datetime"
          python_type: "datetime.datetime"
          serializer: "{value}.isoformat()"
          deserializer: "datetime.datetime.fromisoformat({value})"
   inherit:
     - inherit: "utils.Client[{Input}, {Response}]"
       import: "import utils"
   python_version: "3.10"


Install
-------

Use ``pip`` for install:

.. code-block:: console

    $ pip install git+https://github.com/s1s5/python-graphql-compiler.git

If you want to setup a development environment, use ``poetry`` instead:

.. code-block:: console

    $ # Clone repository
    $ git clone https://github.com/s1s5/python-graphql-compiler.git
    $ cd python-graphql-compiler/

    $ # Install dependencies and hooks
    $ poetry install
    $ poetry run pre-commit install

Credits
-------

This package was created with Cookiecutter_ and the `elbakramer/cookiecutter-poetry`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`elbakramer/cookiecutter-poetry`: https://github.com/elbakramer/cookiecutter-poetry
