import inspect
import tempfile
import unittest

# from click.testing import CliRunner
from graphql import build_ast_schema, parse

from python_graphql_compiler import cli
from python_graphql_compiler.types import Config


class Test(unittest.TestCase):
    def test_cli(self):
        schema_str = """
        type A {
            id: ID!
            name: String
        }
        type Query {
            a(id: ID!): A
        }
        """
        query_str = """
        query Q($id: ID!) {
            a(id: $id) {
                id name
            }
        }
        """
        schema = build_ast_schema(parse(schema_str))

        query_file = tempfile.NamedTemporaryFile()
        query_file.write(query_str.encode("utf-8"))
        query_file.flush()

        out_file = tempfile.NamedTemporaryFile()

        config: Config = {
            "output_path": out_file.name,
            "scalar_map": {},
            "query_ext": "graphql",
            "inherit": [],
        }

        cli.run(schema, [query_file.name], config)

        # print(out_file.read().decode('utf-8'))

    def test_extract_query_files(self):
        # TODO
        pass

    def test_load_config_file(self):
        with tempfile.NamedTemporaryFile() as config_file:
            config_file.write(
                inspect.cleandoc(
                    """
            inherit:
              - inherit: "utils.Client[{Input}, {Response}]"
                import: "import utils"
            """
                ).encode("utf-8")
            )
            config_file.flush()

            config = cli.load_config_file(config_file.name)
            self.assertEqual(
                config["inherit"],
                [{"inherit": "utils.Client[{Input}, {Response}]", "import": "import utils"}],
            )

    def test_main(self):
        pass  # TODO
        # runner = CliRunner()
        # result = runner.invoke(cli.main, ["Peter"])
        # assert result.exit_code == 0
        # assert result.output == "Hello Peter!\n"
