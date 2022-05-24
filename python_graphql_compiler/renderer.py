import copy
import functools
import inspect

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Union
from xmlrpc.client import boolean

from graphql import (
    GraphQLEnumType,
    GraphQLInputObjectType,
    GraphQLList,
    GraphQLNonNull,
    ListTypeNode,
    NamedTypeNode,
    NonNullTypeNode,
    TypeNode,
    Undefined,
)

from .code_chunk import CodeChunk
from .parser import (
    GraphQLOutputType,
    ParsedField,
    ParsedQuery,
    ParsedQueryVariable,
    strip_output_type_attribute,
)
from .render_util import write_file_header, write_typed_dict
from .types import InheritConfig, ScalarConfig

DEFAULT_SCALAR_CONFIG: Dict[str, ScalarConfig] = {
    "Int": {"python_type": "int", "deserializer": "int({value})"},
    "Float": {
        "python_type": "float",
        "deserializer": "float({value})",
    },
    "String": {"python_type": "str"},
    "Boolean": {"python_type": "str"},
    "ID": {"python_type": "str"},
}


@dataclass
class FieldInfo:
    name: str
    graphql_type: GraphQLOutputType
    json_type: str
    python_type: str
    scalar_config: Optional[ScalarConfig]
    serializer: Optional[str] = None
    deserializer: Optional[str] = None
    demangle: List[str] = field(default_factory=list)

    @property
    def need_custom_init(self) -> bool:
        return True

    @property
    def is_scalar(self) -> bool:
        return bool(self.scalar_config)


class DefaultAssignConverter:
    def __init__(self, format_str: Optional[str]):
        self.format_str = format_str

    def __call__(self, varname: str) -> str:
        if self.format_str:
            return self.format_str.format(value=varname)
        return varname


@dataclass
class ObjectAssignConverter:
    field_type_str: str
    demangle: List[str]

    def __call__(self, varname: str) -> str:

        if self.demangle:
            arg = f"demangle({varname}, {self.demangle})"
        else:
            arg = varname
        return f"{self.field_type_str}(**{arg})"


@dataclass
class InlineFragmentAssignConverter:
    field_name: str
    field_type_str: str
    demangle: List[str]

    def __call__(self, varname: str) -> str:
        # inline fragmentは__typename必須
        arg = f"demangle({varname}, {self.demangle})"
        return f'__{self.field_name}_map.get({varname}["__typename"]' + f", {self.field_type_str})(**{arg})"


class Renderer:
    scalar_map: Dict[str, ScalarConfig]
    type_map: Dict[str, ParsedField]
    use_demangle: bool

    def __init__(
        self,
        scalar_map: Dict[str, ScalarConfig] = {},
        inherit: List[InheritConfig] = [],
        python_version: str = "3.10",
    ) -> None:
        self.scalar_map = copy.deepcopy(DEFAULT_SCALAR_CONFIG)
        self.scalar_map.update(scalar_map)
        self.__extra_import: Set[str] = set()
        self.inherit = inherit
        self.type_map = {}
        self.use_demangle = False
        self.python_version = tuple(int(x) for x in python_version.split(".")[:2])

    @property
    def use_typing_extensions(self):
        return self.python_version < (3, 10)

    def render(
        self,
        parsed_query_list: List[ParsedQuery],
    ) -> str:
        self.type_map = {}
        self.use_demangle = False

        buffer = CodeChunk()
        write_file_header(buffer)
        buffer.write("import copy")
        buffer.write("import inspect")
        buffer.write("import typing")

        if self.use_typing_extensions:
            buffer.write("import typing_extensions")

        buffer.write("from dataclasses import dataclass")
        inherit_imports = set(inherit["import"] for inherit in self.inherit if "import" in inherit)
        for im in inherit_imports:
            buffer.write(im)
        inherits_base = ", ".join([inherit["inherit"] for inherit in self.inherit])

        import_pos = buffer.tell()
        self.__extra_import.clear()
        rendered = set()

        _start, wrote = buffer.tell(), False
        for query in parsed_query_list:
            for enum_name, enum_type in query.used_enums.items():
                if enum_name not in rendered:
                    rendered.add(enum_name)
                    self.render_enum(buffer, enum_name, enum_type)
                    wrote = True
                    self.scalar_map[enum_name] = {"python_type": enum_name}
        if wrote:
            buffer.insert(_start, ["", "", "#" * 80, "# enum"])

        _start, wrote = buffer.tell(), False
        for query in parsed_query_list:
            for class_name, class_type in reversed(query.used_input_types.items()):
                if class_name not in rendered:
                    if wrote:
                        buffer.write("")
                        buffer.write("")
                    rendered.add(class_name)
                    self.render_input(buffer, class_name, class_type)
                    wrote = True
        if wrote:
            buffer.insert(_start, ["", "", "#" * 80, "# input"])

        self.render_all_classes(buffer, parsed_query_list, rendered)

        for query in parsed_query_list:
            buffer.write("")
            buffer.write("")
            buffer.write("#" * 80)
            buffer.write(f"# {query.name}")
            self.render_class(buffer, f"{query.name}Response", query, query)
            self.render_variable_type(buffer, f"_{query.name}Input", query.variable_map)

            buffer.write("")
            buffer.write("")
            inherits = inherits_base.format(Input=f"_{query.name}Input", Response=f"{query.name}Response")
            if inherits:
                inherits = f"({inherits})"
            with buffer.write_block(f"class {query.name}{inherits}:"):
                with buffer.write_block("_query = inspect.cleandoc('''"):
                    buffer.write_lines(self.get_query_body(query).splitlines())
                buffer.write("''')")

                type_alias_module = "typing"
                if self.use_typing_extensions:
                    type_alias_module = "typing_extensions"
                buffer.write(f"Input: {type_alias_module}.TypeAlias = _{query.name}Input")
                buffer.write(f"Response: {type_alias_module}.TypeAlias = {query.name}Response")

                self.write_serialize(buffer, query)
                self.write_deserialize(buffer, query)

        if self.use_demangle:
            buffer.insert(
                import_pos,
                inspect.cleandoc(
                    """
            def demangle(data, attrs):
                data = copy.copy(data)
                for attr in attrs:
                    data[attr[1:]] = data.pop(attr)
                return data
            """
                ).splitlines(),
            )
            buffer.insert(import_pos, ["", ""])

        buffer.insert(import_pos, [x for x in sorted(self.__extra_import) if x])

        return str(buffer)

    def get_query_body(self, query: ParsedQuery) -> str:
        body = query.query.loc.source.body  # type: ignore
        return body[query.query.loc.start : query.query.loc.end]  # type: ignore

    def render_enum(self, buffer: CodeChunk, name: str, enum_type: GraphQLEnumType):
        enum_list = [f'"{x}"' for x in enum_type.values]
        buffer.write(f"{name} = typing.Literal[{', '.join(enum_list)}]")

    def get_field_info(self, field_name: str, field_value: ParsedField) -> FieldInfo:
        return FieldInfo(
            name=field_name,
            graphql_type=field_value.type,
            json_type="str",
            python_type=self.type_to_string(field_value.type),
            scalar_config=(
                self.get_scalar_config_from_type(field_value.type)
                if self.is_scalar_type(field_value.type)
                else None
            ),
            demangle=list(set(x.name for x in field_value.fields.values() if x.name.startswith("__"))),
        )

    def get_field_type_mapping(
        self,
        parsed_field: Union[ParsedField, ParsedQuery],
        parsed_query: ParsedQuery,
        depth: int = 0,
    ) -> Dict[str, FieldInfo]:
        m = {}
        if isinstance(parsed_field, ParsedField):
            if parsed_field.interface:
                m = self.get_field_type_mapping(
                    parsed_field.interface,
                    parsed_query=parsed_query,
                    depth=depth + 1,
                )

        m.update(
            {
                field_name: self.get_field_info(field_name, field_value)
                for field_name, field_value in parsed_field.fields.items()
            }
        )
        if isinstance(parsed_field, ParsedField) and "__typename" in m:
            name = strip_output_type_attribute(parsed_field.type).name
            types = [f'"{x}"' for x in parsed_query.type_name_mapping[name]]
            types = sorted(types)
            m["__typename"].python_type = f"typing.Literal[{', '.join(types)}]"

        return m

    def is_scalar_type(self, type_: GraphQLOutputType) -> bool:
        if isinstance(type_, GraphQLNonNull):
            return self.is_scalar_type(type_.of_type)
        elif isinstance(type_, GraphQLList):
            return self.is_scalar_type(type_.of_type)
        elif isinstance(type_, GraphQLEnumType):
            return True
        return type_.name in self.scalar_map

    def unwrap_type(self, type_: GraphQLOutputType) -> str:
        if isinstance(type_, GraphQLNonNull):
            return self.unwrap_type(type_.of_type)
        elif isinstance(type_, GraphQLList):
            return self.unwrap_type(type_.of_type)
        elif isinstance(type_, GraphQLEnumType):
            return type_.name
        return type_.name

    def is_scalar_type_from_node_type(self, type_: TypeNode) -> bool:
        if isinstance(type_, NonNullTypeNode):
            return self.is_scalar_type_from_node_type(type_.type)
        elif isinstance(type_, ListTypeNode):
            return self.is_scalar_type_from_node_type(type_.type)
        elif isinstance(type_, NamedTypeNode):
            return type_.name.value in self.scalar_map
        raise Exception("Unknown type node")  # pragma: no cover

    def unwrap_type_node(self, type_: TypeNode) -> str:
        if isinstance(type_, NonNullTypeNode):
            return self.unwrap_type_node(type_.type)
        elif isinstance(type_, ListTypeNode):
            return self.unwrap_type_node(type_.type)
        elif isinstance(type_, NamedTypeNode):
            return type_.name.value
        raise Exception("Unknown type node")  # pragma: no cover

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
        elif isinstance(field_type, GraphQLList):  # and not self.is_scalar_type(field_type):
            item_assign = self.get_assign_field_str(
                buffer, f"{field_name}__iter", field_type.of_type, converter
            )
            assign = f"[{item_assign} for {field_name}__iter in {field_name}]"
            return assign

        assign = converter(field_name)
        if isnull:
            assign = f"{assign} if {field_name} else None"
        return assign

    def get_assign_field_str_type_node(
        self,
        buffer,
        field_name: str,
        field_type: TypeNode,
        converter: Callable[[str], str],
        isnull=True,
    ):

        if isinstance(field_type, NonNullTypeNode):
            return self.get_assign_field_str_type_node(
                buffer, field_name, field_type.type, converter, isnull=False
            )
        elif isinstance(field_type, ListTypeNode):  # and not self.is_scalar_type_from_node_type(field_type):
            item_assign = self.get_assign_field_str_type_node(
                buffer, f"{field_name}__iter", field_type.type, converter
            )
            assign = f"[{item_assign} for {field_name}__iter in {field_name}]"
            return assign

        assign = converter(field_name)
        if isnull:
            assign = f"{assign} if {field_name} else None"
        return assign

    def render_all_classes(self, buffer: CodeChunk, parsed_query_list: List[ParsedQuery], rendered: Set[str]):
        _start, wrote = buffer.tell(), False
        for query in parsed_query_list:
            for class_name, class_info in reversed(query.type_map.items()):
                if class_name not in rendered:
                    if wrote:
                        buffer.write("")
                        buffer.write("")
                    rendered.add(class_name)
                    self.type_map[class_name] = class_info
                    self.render_class(buffer, class_name, class_info, query)
                    wrote = True
        if wrote:
            buffer.insert(_start, ["", "", "#" * 80, "# type"])

    def render_class(
        self,
        buffer: CodeChunk,
        name: str,
        parsed_field: Union[ParsedField, ParsedQuery],
        parsed_query: ParsedQuery,
    ):
        field_mapping = self.get_field_type_mapping(parsed_field, parsed_query)

        buffer.write("@dataclass")
        with buffer.write_block(f"class {name}:"):
            for field_name, field_info in sorted(field_mapping.items()):
                if field_name.startswith("__"):
                    field_name = field_name[1:]

                buffer.write(f"{field_name}: {field_info.python_type}")

            if functools.reduce(lambda x, y: x or y.need_custom_init, field_mapping.values(), False):
                self.render_class_init(buffer, parsed_field, field_mapping)

    def render_class_init(
        self,
        buffer: CodeChunk,
        parsed_field: Union[ParsedField, ParsedQuery],
        field_mapping: Dict[str, FieldInfo],
    ):
        init_args = ", ".join(
            [
                field_name[1:] if field_name.startswith("__") else field_name
                for field_name in sorted(field_mapping)
            ]
        )
        with buffer.write_block(f"def __init__(self, {init_args}):"):
            for field_name, field_info in sorted(field_mapping.items()):
                if field_name.startswith("__"):
                    field_name = field_name[1:]

                field_type_str = self.type_to_string(field_info.graphql_type, type_only=True)
                converter: Callable[[str], str]
                if field_name in parsed_field.fields and parsed_field.fields[field_name].inline_fragments:
                    with buffer.write_block(f"__{field_name}_map = {'{'}"):
                        for t, pf in parsed_field.fields[field_name].inline_fragments.items():
                            buffer.write(f'"{t}": {pf.type.name},')
                    buffer.write(f'{"}"}')
                    converter = InlineFragmentAssignConverter(
                        field_name=field_name,
                        field_type_str=field_type_str,
                        demangle=field_info.demangle,
                    )
                    self.use_demangle = self.use_demangle or bool(field_info.demangle)
                elif not field_info.is_scalar:
                    converter = ObjectAssignConverter(
                        field_type_str=field_type_str, demangle=field_info.demangle
                    )
                    self.use_demangle = self.use_demangle or bool(field_info.demangle)
                elif field_info.scalar_config:
                    converter = DefaultAssignConverter(field_info.scalar_config.get("deserializer"))
                else:
                    raise Exception("Unexpected Error")  # pragma: no cover

                assign = self.get_assign_field_str(buffer, field_name, field_info.graphql_type, converter)
                buffer.write(f"self.{field_name} = {assign}")

    def get_scalar_config_from_type(self, type_: GraphQLOutputType) -> ScalarConfig:
        if isinstance(type_, GraphQLNonNull):
            return self.get_scalar_config_from_type(type_.of_type)  # type: ignore
        elif isinstance(type_, GraphQLList):
            return self.get_scalar_config_from_type(type_.of_type)
        if type_.name in self.scalar_map:
            return self.scalar_map[type_.name]
        return {
            "python_type": type_.name,
        }

    def get_scalar_config_from_type_node(self, type_: TypeNode) -> ScalarConfig:
        if isinstance(type_, NonNullTypeNode):
            return self.get_scalar_config_from_type_node(type_.type)  # type: ignore
        elif isinstance(type_, ListTypeNode):
            return self.get_scalar_config_from_type_node(type_.type)
        elif isinstance(type_, NamedTypeNode):
            if type_.name.value in self.scalar_map:
                return self.scalar_map[type_.name.value]
            return {
                "python_type": type_.name.value,
            }
        raise Exception("Unknown type node")  # pragma: no cover

    def type_to_string(
        self,
        type_: GraphQLOutputType,
        isnull: boolean = True,
        type_only: boolean = False,
    ) -> str:
        if isinstance(type_, GraphQLNonNull):
            return self.type_to_string(type_.of_type, isnull=False, type_only=type_only)  # type: ignore
        elif isinstance(type_, GraphQLList):
            s = self.type_to_string(type_.of_type, type_only=type_only)
            if type_only:
                return s
            else:
                return f"typing.List[{s}]"  # type: ignore
        if type_.name in self.type_map:
            if type_only:
                return type_.name
            if self.type_map[type_.name].inline_fragments:
                name = (
                    type_.name
                    + " | "
                    + " | ".join([f"{type_.name}__{x}" for x in self.type_map[type_.name].inline_fragments])
                )
            else:
                name = type_.name
            return f"typing.Optional[{name}]" if isnull else name

        type_name = self.scalar_map.get(type_.name, {"import": "", "python_type": type_.name})
        self.__extra_import.add(type_name.get("import") or "")
        if isnull and (not type_only):
            return f"typing.Optional[{type_name['python_type']}]"
        return type_name["python_type"]

    def type_node_to_string(self, node: TypeNode, isnull: boolean = True) -> str:
        if isinstance(node, ListTypeNode):
            return f"typing.List[{self.type_node_to_string(node.type)}]"
        elif isinstance(node, NonNullTypeNode):
            return self.type_node_to_string(node.type, isnull=False)
        elif isinstance(node, NamedTypeNode):
            type_name = self.scalar_map.get(node.name.value, {"import": "", "python_type": node.name.value})
            self.__extra_import.add(type_name.get("import") or "")
            if isnull:
                return f"typing.Optional[{type_name['python_type']}]"
            return type_name["python_type"]
        raise Exception("Unknown type node")  # pragma: no cover

    def render_input(self, buffer: CodeChunk, name: str, input_type: GraphQLInputObjectType):
        # TODO: コード共通化
        r: List[str] = []
        nr: List[str] = []
        for key, pqv in input_type.fields.items():  # type: ignore
            type_: GraphQLOutputType = pqv.type  # type: ignore
            s = f'"{key}": {self.type_to_string(type_)}'
            if (pqv.default_value != Undefined) or (not isinstance(type_, GraphQLNonNull)):
                nr.append(s)
            else:
                r.append(s)

        write_typed_dict(buffer, name, r, nr)
        buffer.write("")
        buffer.write("")
        with buffer.write_block(f"def {name}__serialize(data):"):
            buffer.write("ret = copy.copy(data)")
            for key, pqv in input_type.fields.items():
                type_: GraphQLOutputType = pqv.type  # type: ignore
                is_scalar = self.is_scalar_type(type_)
                scalar_config = self.get_scalar_config_from_type(type_)
                if (not is_scalar) or scalar_config.get("serializer"):
                    if is_scalar:
                        converter = DefaultAssignConverter(scalar_config.get("serializer"))
                    else:
                        converter = DefaultAssignConverter(f"{name}__serialize" + "({value})")
                    assign = self.get_assign_field_str(buffer, "x", type_, converter)
                    statement = f'ret["{key}"] = {assign}'

                    if pqv.default_value != Undefined or (not isinstance(type_, GraphQLNonNull)):
                        with buffer.write_block(f'if "{key}" in data:'):
                            buffer.write(f'x = data["{key}"]')
                            buffer.write(statement)
                    else:
                        buffer.write(f'x = data["{key}"]')
                        buffer.write(statement)
            buffer.write("return ret")

    def render_variable_type(
        self, buffer: CodeChunk, name: str, variable_map: Dict[str, ParsedQueryVariable]
    ):
        r: List[str] = []
        nr: List[str] = []
        for key, pqv in variable_map.items():
            s = f'"{key}": {self.type_node_to_string(pqv.type_node)}'
            if pqv.is_undefinedable:
                nr.append(s)
            else:
                r.append(s)

        write_typed_dict(buffer, name, r, nr)

        buffer.write("")
        buffer.write("")
        with buffer.write_block(f"def {name}__serialize(data):"):
            buffer.write("ret = copy.copy(data)")
            for key, pqv in variable_map.items():
                is_scalar = self.is_scalar_type_from_node_type(pqv.type_node)
                scalar_config = self.get_scalar_config_from_type_node(pqv.type_node)
                if (not is_scalar) or scalar_config.get("serializer"):
                    if is_scalar:
                        converter = DefaultAssignConverter(scalar_config.get("serializer"))
                    else:
                        converter = DefaultAssignConverter(
                            f'{scalar_config["python_type"]}__serialize' + "({value})"
                        )
                    assign = self.get_assign_field_str_type_node(buffer, "x", pqv.type_node, converter)
                    statement = f'ret["{key}"] = {assign}'
                    if pqv.is_undefinedable:
                        with buffer.write_block(f"if {key} in data:"):
                            buffer.write(f'x = data["{key}"]')
                            buffer.write(statement)
                    else:
                        buffer.write(f'x = data["{key}"]')
                        buffer.write(statement)
            buffer.write("return ret")

    def write_serialize(self, buffer: CodeChunk, query: ParsedQuery):
        buffer.write("")
        buffer.write("@classmethod")
        with buffer.write_block(f"def serialize(cls, data: _{query.name}Input):"):
            with buffer.write_block("return {"):
                buffer.write(f'"operation_name": "{query.name}",')
                buffer.write('"query": cls._query,')
                buffer.write(f'"variables": _{query.name}Input__serialize(data),')
            buffer.write("}")

    def write_deserialize(self, buffer: CodeChunk, query: ParsedQuery):
        buffer.write("")
        buffer.write("@classmethod")
        with buffer.write_block("def deserialize(cls, data):"):
            buffer.write("return cls.Response(**data)")
