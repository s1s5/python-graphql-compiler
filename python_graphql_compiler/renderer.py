import os
from dataclasses import dataclass
from typing import Callable, Dict, List, Set, Tuple, Union
from xmlrpc.client import boolean

from graphql import (
    GraphQLEnumType,
    GraphQLInputObjectType,
    GraphQLList,
    GraphQLNonNull,
    ListTypeNode,
    NamedTypeNode,
    NonNullTypeNode,
    OperationType,
    TypeNode,
)

from .parser import (
    GraphQLOutputType,
    ParsedField,
    ParsedQuery,
    ParsedQueryVariable,
    strip_output_type_attribute,
)
from .types import ScalarConfig

DEFAULT_MAPPING = {
    "ID": "str",
    "String": "str",
    "Int": "int",
    "Float": "Number",
    "Boolean": "bool",
}


class CodeChunk:
    class Block:
        def __init__(self, codegen: "CodeChunk"):
            self.gen = codegen

        def __enter__(self):
            self.gen.indent()
            return self.gen

        def __exit__(self, *_, **__):  # type: ignore
            self.gen.unindent()

    def __init__(self):
        self.lines: List[str] = []
        self.level = 0

    def indent(self):
        self.level += 1

    def unindent(self):
        if self.level > 0:
            self.level -= 1

    @property
    def indent_string(self):
        return self.level * "    "

    def write(self, value: str):
        if value != "":
            value = self.indent_string + value
        self.lines.append(value)

    def write_lines(self, lines: List[str]):
        for line in lines:
            self.lines.append(self.indent_string + line)

    def block(self):
        return self.Block(self)

    def write_block(self, block_header: str):
        self.write(block_header)
        return self.block()

    def tell(self):
        return len(self.lines)

    def insert(self, pos: int, lines: List[str]):
        self.lines = self.lines[:pos] + lines + self.lines[pos:]

    def __str__(self):
        return os.linesep.join(self.lines)


class DefaultAssignConverter:
    def __call__(self, varname: str) -> str:
        return varname


@dataclass
class ObjectAssignConverter:
    field_type_str: str

    def __call__(self, varname: str) -> str:
        return f"{self.field_type_str}(**rewrite_typename({varname}))"


@dataclass
class InlineFragmentAssignConverter:
    field_name: str
    field_type_str: str

    def __call__(self, varname: str) -> str:
        return (
            f'__{self.field_name}_map.get({varname}["__typename"]'
            f", {self.field_type_str})(**rewrite_typename({varname}))"
        )


class Renderer:
    def __init__(
        self,
        scalar_map: Dict[str, ScalarConfig] = {},
        extra_import: str = "",
        render_as_typed_dict=False,
    ) -> None:
        self.scalar_map: Dict[str, ScalarConfig] = {
            "ID": {
                "import": "",
                "value": "str",
            },
            "Int": {
                "import": "",
                "value": "int",
            },
            "Float": {
                "import": "",
                "value": "float",
            },
            "Boolean": {
                "import": "",
                "value": "bool",
            },
            "String": {
                "import": "",
                "value": "str",
            },
        }
        self.scalar_map.update(scalar_map)
        self.extra_import = extra_import
        self.__extra_import: Set[str] = set()
        self.render_as_typed_dict = render_as_typed_dict

    def render(
        self,
        parsed_query_list: List[ParsedQuery],
    ) -> str:
        buffer = CodeChunk()
        self.write_file_header(buffer)
        buffer.write("import typing")
        if not self.render_as_typed_dict:
            buffer.write("import copy")
            buffer.write("from dataclasses import dataclass")
        buffer.write("from gql import gql, Client")
        if self.extra_import:
            buffer.write(self.extra_import)
        import_pos = buffer.tell()
        self.__extra_import.clear()
        rendered = set()

        if not self.render_as_typed_dict:
            buffer.write("")
            buffer.write("")
            with buffer.write_block("def rewrite_typename(value: typing.Any):"):
                with buffer.write_block("if isinstance(value, dict) and '__typename' in value:"):
                    buffer.write("value = copy.copy(value)")
                    buffer.write("value['_typename'] = value.pop('__typename')")
                buffer.write("return value")
            buffer.write("")

        for query in parsed_query_list:
            for enum_name, enum_type in query.used_enums.items():
                if enum_name in rendered:
                    continue
                rendered.add(enum_name)
                self.render_enum(buffer, enum_name, enum_type)

            for class_name, class_type in reversed(query.used_input_types.items()):
                if class_name in rendered:
                    continue
                rendered.add(class_name)
                self.render_input(buffer, class_name, class_type)

            for class_name, class_info in reversed(query.type_map.items()):
                if class_name in rendered:
                    continue
                rendered.add(class_name)
                if self.render_as_typed_dict:
                    self.render_typed_dict(buffer, class_name, class_info, query)
                else:
                    self.render_class(buffer, class_name, class_info, query)

            if self.render_as_typed_dict:
                self.render_typed_dict(buffer, f"{query.name}Response", query, query)
            else:
                self.render_class(buffer, f"{query.name}Response", query, query)

            self.render_variable_type(buffer, f"_{query.name}Input", query.variable_map)

            buffer.write("")
            buffer.write("")
            with buffer.write_block(f"class {query.name}:"):
                buffer.write(f"Response: typing.TypeAlias = {query.name}Response")
                buffer.write(f"Input: typing.TypeAlias = _{query.name}Input")
                with buffer.write_block("_query = gql('''"):
                    buffer.write_lines(self.get_query_body(query).splitlines())
                buffer.write("''')")
                if query.query.operation in (OperationType.QUERY, OperationType.MUTATION):
                    self.write_execute_method(buffer, query, async_=False)
                    self.write_execute_method(buffer, query, async_=True)
                else:
                    self.write_subscribe_method(buffer, query, async_=False)
                    self.write_subscribe_method(buffer, query, async_=True)

        buffer.insert(import_pos, [x for x in sorted(self.__extra_import) if x])
        return str(buffer)

    def get_query_body(self, query: ParsedQuery) -> str:
        body = query.query.loc.source.body  # type: ignore
        return body[query.query.loc.start : query.query.loc.end]  # type: ignore

    def render_enum(self, buffer: CodeChunk, name: str, enum_type: GraphQLEnumType):
        enum_list = [f'"{x}"' for x in enum_type.values]
        buffer.write(f"{name} = typing.Literal[{', '.join(enum_list)}]")

    def render_input(self, buffer: CodeChunk, name: str, input_type: GraphQLInputObjectType):
        # TODO: コード共通か
        r: List[str] = []
        nr: List[str] = []
        for key, pqv in input_type.fields.items():  # type: ignore
            type_: GraphQLOutputType = pqv.type  # type: ignore
            s = f'"{key}": {self.type_to_string(type_)}'
            if bool(pqv.default_value) or (not isinstance(type_, GraphQLNonNull)):
                nr.append(s)
            else:
                r.append(s)

        buffer.write("")
        buffer.write("")
        buffer.write(f'{name}__required = typing.TypedDict("{name}__required", {"{"}{", ".join(r)}{"}"})')
        buffer.write(
            f'{name}__not_required = typing.TypedDict("{name}__not_required", '
            f'{"{"}{", ".join(nr)}{"}"}, total=False)'
        )
        buffer.write("")
        buffer.write("")
        with buffer.write_block(f"class {name}({name}__required, {name}__not_required):"):
            buffer.write("pass")

    def get_field_type_mapping(
        self, parsed_field: Union[ParsedField, ParsedQuery], parsed_query: ParsedQuery
    ) -> Dict[str, Tuple[GraphQLOutputType, str]]:
        m = {}
        if isinstance(parsed_field, ParsedField):
            if parsed_field.interface:
                m = self.get_field_type_mapping(parsed_field.interface, parsed_query=parsed_query)
        m.update(
            {
                field_name: (field_value.type, self.type_to_string(field_value.type))
                for field_name, field_value in parsed_field.fields.items()
            }
        )
        if isinstance(parsed_field, ParsedField) and "__typename" in m:
            name = strip_output_type_attribute(parsed_field.type).name
            types = [f'"{x}"' for x in parsed_query.type_name_mapping[name]]
            types = sorted(types)
            m["__typename"] = (m["__typename"][0], f"typing.Literal[{', '.join(types)}]")
        return m

    def is_scalar_type(self, type_: GraphQLOutputType) -> bool:
        if isinstance(type_, GraphQLNonNull):
            return self.is_scalar_type(type_.of_type)
        elif isinstance(type_, GraphQLList):
            return self.is_scalar_type(type_.of_type)
        elif isinstance(type_, GraphQLEnumType):
            return True
        return type_.name in self.scalar_map

    def get_assign_field_str(
        self,
        buffer,
        field_name: str,
        field_type: GraphQLOutputType,
        converter: Callable[[str], str],
        isnull=True,
    ):
        if isinstance(field_type, GraphQLNonNull):
            return self.get_assign_field_str(buffer, field_name, field_type.of_type, converter, isnull=False)
        elif isinstance(field_type, GraphQLList) and not self.is_scalar_type(field_type):
            item_assign = self.get_assign_field_str(
                buffer, f"{field_name}__iter", field_type.of_type, converter
            )
            assign = f"[{item_assign} for {field_name}__iter in {field_name}]"
            return assign

        assign = converter(field_name)
        if isnull:
            assign = f"{assign} if {field_name} else None"
        return assign

    def render_class(
        self,
        buffer: CodeChunk,
        name: str,
        parsed_field: Union[ParsedField, ParsedQuery],
        parsed_query: ParsedQuery,
    ):
        field_mapping = self.get_field_type_mapping(parsed_field, parsed_query)
        if "__typename" in field_mapping:
            field_mapping["_typename"] = field_mapping.pop("__typename")

        buffer.write("")
        buffer.write("")
        buffer.write("@dataclass")
        with buffer.write_block(f"class {name}:"):
            has_object = False
            for field_name, (field_type, field_type_str) in field_mapping.items():
                buffer.write(f"{field_name}: {field_type_str}")
                if not self.is_scalar_type(field_type):
                    has_object = True
            if has_object:
                init_args = ", ".join([field_name for field_name in field_mapping])
                with buffer.write_block(f"def __init__(self, {init_args}):"):
                    for field_name, (field_type, field_type_str) in field_mapping.items():
                        field_type_str = self.type_to_string(field_type, type_only=True)
                        converter: Callable[[str], str] = DefaultAssignConverter()
                        if (
                            field_name in parsed_field.fields
                            and parsed_field.fields[field_name].inline_fragments
                        ):
                            with buffer.write_block(f"__{field_name}_map = {'{'}"):
                                for t, pf in parsed_field.fields[field_name].inline_fragments.items():
                                    buffer.write(f'"{t}": {pf.type.name},')
                            buffer.write(f'{"}"}')
                            converter = InlineFragmentAssignConverter(
                                field_name=field_name, field_type_str=field_type_str
                            )
                            # converter = lambda varname: (
                            #     f'__{field_name}_map.get({varname}["__typename"]'
                            #     f", {field_type_str})(**rewrite_typename({varname}))"
                            # )
                        elif not self.is_scalar_type(field_type):
                            converter = ObjectAssignConverter(field_type_str=field_type_str)
                            # converter = lambda varname: f"{field_type_str}(**rewrite_typename({varname}))"

                        assign = self.get_assign_field_str(buffer, field_name, field_type, converter)
                        buffer.write(f"self.{field_name} = {assign}")

            # if isinstance(parsed_field, ParsedField):
            #     if parsed_field.inline_fragments:
            #         print("has, inline fields: ", parsed_field.inline_fragments)

    def render_typed_dict(
        self,
        buffer: CodeChunk,
        name: str,
        parsed_field: Union[ParsedField, ParsedQuery],
        parsed_query: ParsedQuery,
    ):
        field_mapping = self.get_field_type_mapping(parsed_field, parsed_query)
        r = [f'"{key}": {value}' for key, (_, value) in field_mapping.items()]
        buffer.write("")
        buffer.write("")
        type_str = f'typing.TypedDict("{name}", {"{"}{", ".join(r)}{"}"})'
        if isinstance(parsed_field, ParsedField):
            if parsed_field.inline_fragments:
                type_str = f'typing.TypedDict("__{name}", {"{"}{", ".join(r)}{"}"})'
                buffer.write(f"__{name} = {type_str}")
                types = [
                    f"{strip_output_type_attribute(parsed_field.type).name}__{x}"
                    for x in parsed_field.inline_fragments
                ]
                type_str = f"typing.Union[__{name}, {', '.join(types)}]"
        buffer.write(f"{name} = {type_str}")

    def type_to_string(
        self, type_: GraphQLOutputType, isnull: boolean = True, type_only: boolean = False
    ) -> str:
        if isinstance(type_, GraphQLNonNull):
            return self.type_to_string(type_.of_type, isnull=False, type_only=type_only)  # type: ignore
        elif isinstance(type_, GraphQLList):
            s = self.type_to_string(type_.of_type, type_only=type_only)
            if type_only:
                return s
            else:
                return f"typing.List[{s}]"  # type: ignore
        type_name = self.scalar_map.get(type_.name, {"import": "", "value": type_.name})
        self.__extra_import.add(type_name["import"])
        if isnull and (not type_only):
            return f"typing.Optional[{type_name['value']}]"
        return type_name["value"]

    def node_type_to_string(self, node: TypeNode, isnull: boolean = True) -> str:
        if isinstance(node, ListTypeNode):
            return f"typing.List[{self.node_type_to_string(node.type)}]"
        elif isinstance(node, NonNullTypeNode):
            return self.node_type_to_string(node.type, isnull=False)
        elif isinstance(node, NamedTypeNode):
            type_name = self.scalar_map.get(node.name.value, {"import": "", "value": node.name.value})
            self.__extra_import.add(type_name["import"])
            if isnull:
                return f"typing.Optional[{type_name['value']}]"
            return type_name["value"]
        raise Exception("Unknown type node")  # pragma: no cover

    def render_variable_type(
        self, buffer: CodeChunk, name: str, variable_map: Dict[str, ParsedQueryVariable]
    ):
        r: List[str] = []
        nr: List[str] = []
        for key, pqv in variable_map.items():
            s = f'"{key}": {self.node_type_to_string(pqv.type_node)}'
            if pqv.is_undefinedable:
                nr.append(s)
            else:
                r.append(s)

        buffer.write("")
        buffer.write("")
        buffer.write(f'{name}__required = typing.TypedDict("{name}__required", {"{"}{", ".join(r)}{"}"})')
        buffer.write(
            f'{name}__not_required = typing.TypedDict("{name}__not_required", '
            f'{"{"}{", ".join(nr)}{"}"}, total=False)'
        )
        buffer.write("")
        buffer.write("")
        with buffer.write_block(f"class {name}({name}__required, {name}__not_required):"):
            buffer.write("pass")

    def write_execute_method(
        self,
        buffer: CodeChunk,
        query: ParsedQuery,
        async_: bool,
    ) -> None:
        buffer.write("@classmethod")
        var_list: List[str] = []
        for variable in query.query.variable_definitions:
            var_type_str = self.node_type_to_string(variable.type)
            var_list.append(f"{variable.variable.name.value}: {var_type_str}")

        default_variable_values = ""
        if all(x.is_undefinedable for x in query.variable_map.values()):
            default_variable_values = " = {}"
        method_name = f"execute{'_async' if async_ else ''}"

        response_type = f"{query.name}Response"
        async_prefix = "async " if ((not self.render_as_typed_dict) and async_) else ""

        if async_ and (not async_prefix):
            response_type = f"typing.Awaitable[{response_type}]"

        with buffer.write_block(
            f"{async_prefix}def {method_name}(cls, client: Client, "
            f"variable_values: _{query.name}Input{default_variable_values})"
            f" -> {response_type}:"
        ):
            extra_closure = "" if self.render_as_typed_dict else "))"
            if self.render_as_typed_dict:
                buffer.write(f"return client.{method_name}(  # type: ignore")
            else:
                await_prefix = "await " if async_prefix else ""
                buffer.write(
                    "return cls.Response(**rewrite_typename("
                    f"{await_prefix}client.{method_name}(  # type: ignore"
                )
            buffer.write("    cls._query, variable_values=variable_values")
            buffer.write(f"){extra_closure}")

    def write_subscribe_method(self, buffer: CodeChunk, query: ParsedQuery, async_: bool) -> None:
        buffer.write("@classmethod")
        var_list: List[str] = []
        for variable in query.query.variable_definitions:
            var_type_str = self.node_type_to_string(variable.type)
            var_list.append(f"{variable.variable.name.value}: {var_type_str}")

        default_variable_values = ""
        if all(x.is_undefinedable for x in query.variable_map.values()):
            default_variable_values = " = {}"
        method_name = f"subscribe{'_async' if async_ else ''}"
        async_prefix = "async " if async_ else ""
        response_type = f"typing.Iterable[{query.name}Response]"
        if async_:
            response_type = f"typing.AsyncIterable[{query.name}Response]"
        with buffer.write_block(
            f"{async_prefix}def {method_name}(cls, client: Client, "
            f"variable_values: _{query.name}Input{default_variable_values})"
            f" -> {response_type}:"
        ):
            with buffer.write_block(
                f"{async_prefix}for r in client.{method_name}("
                "cls._query, variable_values=variable_values):  # type: ignore"
            ):
                if self.render_as_typed_dict:
                    buffer.write("yield r  # type: ignore")
                else:
                    buffer.write("yield cls.Response(**rewrite_typename(r))  # type: ignore")

    @staticmethod
    def write_file_header(buffer: CodeChunk) -> None:
        buffer.write("# @" + "generated AUTOGENERATED file. Do not Change!")
        buffer.write("# flake8: noqa")
        buffer.write("# fmt: off")
        buffer.write("# isort: skip_file")
        buffer.write("")
