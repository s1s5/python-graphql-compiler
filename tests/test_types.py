import unittest

from python_graphql_compiler import types


class Test(unittest.TestCase):
    def test_type(self):
        a: types.Config = {  # noqa
            "output_path": "",
            "scalar_map": {},
            "query_ext": "",
            "inherit": [],
        }
