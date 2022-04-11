import unittest

from graphql import (
    GraphQLEnumType,
    GraphQLInputObjectType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    NamedTypeNode,
    NonNullTypeNode,
    OperationDefinitionNode,
    build_ast_schema,
)
from graphql.language.parser import parse

from python_graphql_compiler.parser import ParsedField, ParsedQuery, Parser


class Test(unittest.TestCase):
    def test_field(self):
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

        parsed_query = parse(query_str)
        query = parsed_query.definitions[0]
        assert isinstance(query, OperationDefinitionNode)
        parser = Parser(schema)

        result = parser.parse(query)

        self.assertTrue(isinstance(result, ParsedQuery))
        self.assertEqual(result.name, "Q")
        self.assertEqual(len(result.fields), 1)

        field = result.fields["a"]
        self.assertTrue(isinstance(field, ParsedField))
        self.assertEqual(field.name, "a")
        self.assertTrue(isinstance(field.type, GraphQLObjectType))
        self.assertEqual(field.type.name, "Q__a")
        self.assertEqual(list(field.fields.keys()), ["id", "name"])

        q__a__id = field.fields["id"]
        self.assertTrue(isinstance(q__a__id.type, GraphQLNonNull))
        self.assertTrue(isinstance(q__a__id.type.of_type, GraphQLScalarType))  # type: ignore
        self.assertEqual(q__a__id.type.of_type.name, "ID")  # type: ignore

        q__a__name = field.fields["name"]
        self.assertTrue(isinstance(q__a__name.type, GraphQLScalarType))
        self.assertEqual(q__a__name.type.name, "String")

        self.assertEqual(result.type_map["Q__a"], field)

        self.assertEqual(len(result.variable_map), 1)
        v_id = result.variable_map["id"]
        self.assertFalse(v_id.is_undefinedable)
        if isinstance(v_id.type_node, NonNullTypeNode):
            _type = v_id.type_node.type
            self.assertTrue(isinstance(_type, NamedTypeNode))
            self.assertEqual(_type.name.value, "ID")  # type: ignore
        else:
            self.assertTrue(False)

    def test_inline_fragment(self):
        schema_str = """
        interface I {
            id: ID!
            name: String
        }
        type A implements I {
            id: ID!
            name: String
            a: Int!
        }
        type B implements I {
            id: ID!
            name: String
            b: String
        }
        type Query {
            i: I
        }
        """
        query_str = """
        query Q {
            i {
                __typename id
                ... on A {a}
                ... on B {b}
            }
        }
        """
        schema = build_ast_schema(parse(schema_str))

        parsed_query = parse(query_str)
        query = parsed_query.definitions[0]
        assert isinstance(query, OperationDefinitionNode)
        parser = Parser(schema)

        result = parser.parse(query)

        # ParsedQuery(
        #     query=OperationDefinitionNode at 9:146,
        #     name='Q',
        #     variable_definitions=[],
        #     fields={
        #         'i': ParsedField(
        #             name='i',
        #             type=<GraphQLInterfaceType 'Q__i'>,
        #             node=FieldNode at 31:136,
        #             fields={
        #                 '__typename': ParsedField(
        #                     name='__typename',
        #                     type=<GraphQLNonNull <GraphQLScalarType 'String'>>,
        #                     node=FieldNode at 51:61,
        #                     fields={},
        #                     inline_fragments={},
        #                     interface=None
        #                 ),
        #                 'id': ParsedField(
        #                     name='id',
        #                     type=<GraphQLNonNull <GraphQLScalarType 'ID'>>,
        #                     node=FieldNode at 62:64,
        #                     fields={},
        #                     inline_fragments={},
        #                     interface=None
        #                 )
        #             },
        #             inline_fragments={
        #                 'A': ParsedField(
        #                     name='A',
        #                     type=<GraphQLObjectType 'Q__i__A'>,
        #                     node=InlineFragmentNode at 81:93,
        #                     fields={
        #                         'a': ParsedField(
        #                             name='a',
        #                             type=<GraphQLNonNull <GraphQLScalarType 'Int'>>,
        #                             node=FieldNode at 91:92,
        #                             fields={},
        #                             inline_fragments={},
        #                             interface=None
        #                         )
        #                     },
        #                     inline_fragments={},
        #                     interface=...
        #                 ),
        #                 'B': ParsedField(
        #                     name='B',
        #                     type=<GraphQLObjectType 'Q__i__B'>,
        #                     node=InlineFragmentNode at 110:122,
        #                     fields={
        #                         'b': ParsedField(
        #                             name='b',
        #                             type=<GraphQLScalarType 'String'>,
        #                             node=FieldNode at 120:121,
        #                             fields={},
        #                             inline_fragments={},
        #                             interface=None
        #                         )
        #                     },
        #                     inline_fragments={},
        #                     interface=...
        #                 )
        #             },
        #             interface=None
        #         )
        #     },
        #     type_map=OrderedDict([
        #         ('Q__i', ParsedField(...)),
        #         ('Q__i__A', ParsedField...)),
        #         ('Q__i__B', ParsedField(...)))]),
        #     used_input_types={},
        #     used_enums={},
        #     variable_map=OrderedDict(),
        #     type_name_mapping={'Q__i': {'I'}, 'Q__i__A': {'A'}, 'Q__i__B': {'B'}}
        # )

        self.assertEqual(result.name, "Q")
        self.assertEqual(len(result.fields), 1)

        field = result.fields["i"]

        self.assertEqual(len(field.inline_fragments), 2)

        a = field.inline_fragments["A"]
        self.assertEqual(a.name, "A")
        self.assertEqual(a.type.name, "Q__i__A")
        self.assertEqual(list(a.fields.keys()), ["a"])

        b = field.inline_fragments["B"]
        self.assertEqual(b.name, "B")
        self.assertEqual(b.type.name, "Q__i__B")
        self.assertEqual(list(b.fields.keys()), ["b"])

    def test_union(self):
        schema_str = """
        type A {
            a: String
        }
        type B {
            b: Int
        }

        union AB = A | B

        type Query {
            ab: AB
        }
        """
        query_str = """
        query Q {
            ab {
                __typename
                ... on A { a }
                ... on B { b }
            }
        }
        """
        schema = build_ast_schema(parse(schema_str))

        parsed_query = parse(query_str)
        query = parsed_query.definitions[0]
        assert isinstance(query, OperationDefinitionNode)
        parser = Parser(schema)

        result = parser.parse(query)

        self.assertEqual(result.name, "Q")
        self.assertEqual(len(result.fields), 1)

        field = result.fields["ab"]

        self.assertEqual(len(field.inline_fragments), 2)

        a = field.inline_fragments["A"]
        self.assertEqual(a.name, "A")
        self.assertEqual(a.type.name, "Q__ab__A")
        self.assertEqual(list(a.fields.keys()), ["a"])

        b = field.inline_fragments["B"]
        self.assertEqual(b.name, "B")
        self.assertEqual(b.type.name, "Q__ab__B")
        self.assertEqual(list(b.fields.keys()), ["b"])

    def test_enum(self):
        schema_str = """
        enum E{
            X
            Y
            Z
        }
        type A {
            e: E
        }
        type Query {
            a(e: E!): A
        }
        """
        query_str = """
        query Q($e: E!) {
            a(e: $e) {
               e
            }
        }
        """
        schema = build_ast_schema(parse(schema_str))

        parsed_query = parse(query_str)
        query = parsed_query.definitions[0]
        assert isinstance(query, OperationDefinitionNode)
        parser = Parser(schema)

        result = parser.parse(query)

        e = result.fields["a"].fields["e"]
        self.assertEqual(e.name, "e")
        self.assertTrue(isinstance(e.type, GraphQLEnumType))

        self.assertEqual(len(result.used_enums), 1)
        E = result.used_enums["E"]
        if isinstance(E, GraphQLEnumType):
            self.assertEqual(list(E.values.keys()), ["X", "Y", "Z"])
        else:
            self.assertTrue(False)

    def test_list(self):
        schema_str = """
        type A {
            l: [[String]]
        }
        type Query {
            a(l: [ID]): A
        }
        """
        query_str = """
        query Q($l: [ID]) {
            a(l: $l) {
               l
            }
        }
        """
        schema = build_ast_schema(parse(schema_str))

        parsed_query = parse(query_str)
        query = parsed_query.definitions[0]
        assert isinstance(query, OperationDefinitionNode)
        parser = Parser(schema)

        result = parser.parse(query)

        x = result.fields["a"].fields["l"]
        if isinstance(x.type, GraphQLList):
            if isinstance(x.type.of_type, GraphQLList):
                self.assertTrue(isinstance(x.type.of_type.of_type, GraphQLScalarType))
                self.assertEqual(x.type.of_type.of_type.name, "String")
            else:
                self.assertTrue(False)
        else:
            self.assertTrue(False)

    def test_input_object_type(self):
        schema_str = """
        input A {
            name: String
        }
        input B {
            a: A
        }
        type C {
            name: String
        }
        type Query {
            c(b: B): C
        }
        """
        query_str = """
        query Q($b: B) {
            c(b: $b) {
               name
            }
        }
        """
        schema = build_ast_schema(parse(schema_str))

        parsed_query = parse(query_str)
        query = parsed_query.definitions[0]
        assert isinstance(query, OperationDefinitionNode)
        parser = Parser(schema)

        result = parser.parse(query)
        self.assertEqual(len(result.used_input_types), 2)
        B = result.used_input_types["B"]
        self.assertTrue(isinstance(B, GraphQLInputObjectType))
        self.assertEqual(B.name, "B")
        self.assertEqual(list(B.fields.keys()), ["a"])

    def test_must_add_typename(self):
        schema_str = """
        interface I {
            id: ID!
        }
        type A implements I {
            id: ID!
            a: Int!
        }
        type B implements I {
            id: ID!
            b: String
        }
        type Query {
            i: I
        }
        """
        query_str = """
        query Q {
            i {
                ... on A {a}
                ... on B {b}
            }
        }
        """
        schema = build_ast_schema(parse(schema_str))

        parsed_query = parse(query_str)
        query = parsed_query.definitions[0]
        assert isinstance(query, OperationDefinitionNode)
        parser = Parser(schema)
        with self.assertRaises(Exception):
            parser.parse(query)
