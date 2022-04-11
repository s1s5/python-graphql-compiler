import glob
import json
import os

from collections import defaultdict
from typing import Dict, List, Optional, Set

import click
import requests
import yaml

from graphql import GraphQLSchema, build_ast_schema, get_introspection_query, validate
from graphql.language import FragmentDefinitionNode, OperationDefinitionNode
from graphql.language.parser import parse
from graphql.utilities.print_schema import print_schema
from graphql.validation.rules.no_unused_fragments import NoUnusedFragmentsRule
from graphql.validation.specified_rules import specified_rules

import python_graphql_compiler

from .parser import Parser
from .renderer import Renderer
from .types import Config
from .utils import build_client_schema

DEFAULT_CONFIG: Config = {
    "output_path": "{dirname}/{basename_without_ext}.py",
    "scalar_map": {
        "Date": {
            "import": "import datetime",
            "python_type": "datetime.date",
            "serializer": "{value}.isoformat()",
            "deserializer": "datetime.date.fromisoformat({value})",
        },
        "DateTime": {
            "import": "import datetime",
            "python_type": "datetime.datetime",
            "serializer": "{value}.isoformat()",
            "deserializer": "datetime.datetime.fromisoformat({value})",
        },
        "Time": {
            "import": "import datetime",
            "python_type": "datetime.time",
            "serializer": "{value}.isoformat()",
            "deserializer": "datetime.time.fromisoformat({value})",
        },
        "UUID": {
            "import": "import uuid",
            "python_type": "uuid.UUID",
            "serializer": "str({value})",
            "deserializer": "uuid.UUID({value})",
        },
    },
    "query_ext": "graphql",
    "inherit": [],
}


def run(
    schema: GraphQLSchema,
    query_files: List[str],
    config: Config,
) -> None:
    query_parser = Parser(schema)
    query_renderer = Renderer(
        scalar_map=config["scalar_map"],
        inherit=config["inherit"],
    )

    operation_library: Dict[str, List[OperationDefinitionNode]] = defaultdict(list)
    fragment_library: Dict[str, List[FragmentDefinitionNode]] = defaultdict(list)

    rules = [rule for rule in specified_rules if rule is not NoUnusedFragmentsRule]
    for filename in query_files:
        with open(filename, "r", encoding="utf-8") as fp:
            parsed_query = parse(fp.read())
        errors = validate(schema, parsed_query, rules)
        if errors:
            raise Exception(errors)
        for definition in parsed_query.definitions:
            if isinstance(definition, OperationDefinitionNode):
                assert definition.name
                operation_library[filename].append(definition)
            elif isinstance(definition, FragmentDefinitionNode):
                assert definition.name
                fragment_library[filename].append(definition)

    for filename, definition_list in operation_library.items():
        parsed_list = [query_parser.parse(definition) for definition in definition_list]

        if config.get("output_path"):
            dirname = os.path.dirname(filename)
            basename = os.path.basename(filename)
            basename_without_ext, ext = os.path.splitext(basename)
            dst_path = config["output_path"].format(
                dirname=dirname,
                basename=basename,
                basename_without_ext=basename_without_ext,
                ext=ext,
            )
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            with open(dst_path, "w") as fp:
                print(query_renderer.render(parsed_list), file=fp)


def compile_schema_library(schema_filepaths: Optional[List[str]]) -> GraphQLSchema:
    if not schema_filepaths:
        raise Exception("schema must be required")

    full_schema = ""
    for schema_filepath in schema_filepaths:
        if schema_filepath.startswith("http"):
            res = requests.post(
                schema_filepath,
                headers={"Content-Type": "application/json"},
                data=json.dumps({"query": get_introspection_query()}),
            )
            res.raise_for_status()
            full_schema = full_schema + print_schema(build_client_schema(res.json()["data"]))
        else:
            with open(schema_filepath) as schema_file:
                full_schema = full_schema + schema_file.read()

    return build_ast_schema(parse(full_schema))


def extract_query_files(queries: Optional[List[str]], config: Config) -> List[str]:
    if not queries:
        raise Exception("query file must be required")

    results: Set[str] = set()
    for pattern in queries:
        for f_or_d in glob.glob(pattern):
            if not os.path.exists(f_or_d):
                continue
            if os.path.isfile(f_or_d):
                results.add(f_or_d)
            if os.path.isdir(f_or_d):
                results.update(glob.glob(os.path.join(f_or_d, f'**/*.{config["query_ext"]}')))
    return list(results)


def load_config_file(config_file: Optional[str]) -> Config:
    config = DEFAULT_CONFIG
    if config_file:
        with open(config_file) as fp:
            config.update(yaml.safe_load(fp))
    return config


@click.command()
@click.option(
    "-s",
    "--schema",
    help="the graphql schemas storage path or url",
    type=str,
    multiple=True,
)
@click.option(
    "-q",
    "--query",
    help="path where query file or directory all queries files are stored",
    type=str,
    multiple=True,
)
@click.option("-c", "--config", help="path where config yaml file", type=str)
@click.version_option(python_graphql_compiler.__version__, "--version")
def cli(
    schema: List[str],
    query: List[str],
    config: Optional[str],
):
    compiled_schema = compile_schema_library(schema)
    config_data = load_config_file(config)
    query_files = extract_query_files(query, config_data)

    run(
        schema=compiled_schema,
        query_files=query_files,
        config=config_data,
    )


def main():
    # pylint: disable=no-value-for-parameter
    cli()  # noqa


if __name__ == "__main__":
    main()
