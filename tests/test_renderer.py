import inspect
import unittest

from typing import Optional

from graphql import GraphQLList, OperationDefinitionNode, build_ast_schema, parse

from python_graphql_compiler import renderer
from python_graphql_compiler.parser import ParsedQuery, Parser


def get_parsed_query(query_str: str, schema_str: Optional[str] = None) -> ParsedQuery:
    if schema_str is None:
        schema_str = """
        enum Episode {
            NEWHOPE
            EMPIRE
            JEDI
        }
        input SubInput {
            age: Int
        }
        input AddInput {
            name: String!
            sub: SubInput
        }
        type A {
            id: ID!
            name: String
            episode: Episode!
            llll: [[[[String]]]]
            r: SearchResult
        }
        union SearchResult = Human | Droid | Starship

        interface Character {
            id: ID!
            name: String!
            appearsIn: [Episode!]!
            bestFriend: Character
            friends: [Character]
        }
        type Human implements Character {
            id: ID!
            name: String!
            appearsIn: [Episode!]!
            bestFriend: Character
            friends: [Character]
            totalCredits: Int!
            starshipIds: [ID!]!
            starships: [Starship]
        }
        type Droid implements Character {
            id: ID!
            name: String!
            appearsIn: [Episode!]!
            bestFriend: Character
            friends: [Character]
            primaryFunction: String!
        }

        type Starship {
            id: ID!
            name: String!
        }

        type Query {
            hello: String!
            a(id: ID!): A
            a2(llll: [[[[String]]]]): A
            hero: Character
        }
        type Mutation {
            add(input: AddInput!): A
        }
        type Subscription {
            count(target: Int!): String
        }
        """

    schema = build_ast_schema(parse(schema_str))
    parsed_query = parse(query_str)
    query = parsed_query.definitions[0]
    assert isinstance(query, OperationDefinitionNode)
    parser = Parser(schema)
    return parser.parse(query)


class Test(unittest.TestCase):
    def test_code_chunk(self):
        cc = renderer.CodeChunk()
        cc.write("a")
        line_index = cc.tell()
        with cc.write_block("b"):
            cc.write_lines(["c"])
        cc.insert(line_index, ["d"])
        self.assertEqual(
            str(cc),
            inspect.cleandoc(
                """
                a
                d
                b
                    c
                """
            ),
        )

    def test_render(self):
        parsed_query = get_parsed_query(
            """
            query Q {
                hero {
                    __typename
                    name
                    appearsIn
                    bestFriend {
                        name
                    }
                    friends {
                        __typename
                        ... on Human {
                            name
                        }
                        ... on Droid {
                            primaryFunction
                        }
                    }
                }
            }
            """
        )

        r = renderer.Renderer()
        r.render([parsed_query])

    def test_get_query_body(self):
        parsed_query = get_parsed_query(
            """
            # comment
            query Q {
                hello
            }
            # other-comment
            """
        )

        r = renderer.Renderer()
        body = r.get_query_body(parsed_query)
        self.assertEqual(
            body,
            """query Q {
                hello
            }""",
        )

    def test_render_enum(self):
        parsed_query = get_parsed_query(
            """
            query Q($id: ID!) {
                a(id: $id) {
                    episode
                }
            }
            """
        )

        b = renderer.CodeChunk()
        r = renderer.Renderer()
        r.render_enum(b, "Episode", parsed_query.used_enums["Episode"])
        self.assertEqual(str(b), 'Episode = typing.Literal["NEWHOPE", "EMPIRE", "JEDI"]')

    def test_render_input(self):
        parsed_query = get_parsed_query(
            """
            mutation M($input: AddInput!) {
                add(input: $input) {
                    name
                }
            }
            """
        )
        b = renderer.CodeChunk()
        r = renderer.Renderer()
        r.render_input(b, "SubInput", parsed_query.used_input_types["SubInput"])
        r.render_input(b, "AddInput", parsed_query.used_input_types["AddInput"])

        self.assertEqual(
            str(b).strip(),
            inspect.cleandoc(
                """
                SubInput__required = typing.TypedDict("SubInput__required", {})
                SubInput__not_required = typing.TypedDict("SubInput__not_required", {"age": typing.Optional[int]}, total=False)


                class SubInput(SubInput__required, SubInput__not_required):
                    pass


                def SubInput__serialize(data):
                    ret = copy.copy(data)
                    return ret


                AddInput__required = typing.TypedDict("AddInput__required", {"name": str})
                AddInput__not_required = typing.TypedDict("AddInput__not_required", {"sub": typing.Optional[SubInput]}, total=False)


                class AddInput(AddInput__required, AddInput__not_required):
                    pass


                def AddInput__serialize(data):
                    ret = copy.copy(data)
                    x = data["sub"]
                    ret["sub"] = AddInput__serialize(x) if x else None
                    return ret
                """  # noqa
            ),
        )

    def test_get_field_type_mapping(self):
        parsed_query = get_parsed_query(
            """
            query Q {
                hero {
                    __typename
                    ... on Human {
                        friends {
                            __typename
                            ... on Human {
                                name
                            }
                            ... on Droid {
                                primaryFunction
                            }
                        }
                    }
                }
            }
            """
        )

        r = renderer.Renderer()
        m = r.get_field_type_mapping(parsed_query.fields["hero"], parsed_query)
        # {'__typename': (
        #     <GraphQLNonNull <GraphQLScalarType 'String'>>, 'typing.Literal["Character", "Droid"]')}
        self.assertEqual(m["__typename"].python_type, 'typing.Literal["Character", "Droid"]')

        m = r.get_field_type_mapping(parsed_query.fields["hero"].inline_fragments["Human"], parsed_query)
        # {'__typename': (<GraphQLNonNull <GraphQLScalarType 'String'>>, 'typing.Literal["Human"]'),
        #  'friends': (<GraphQLList <GraphQLInterfaceType 'Q__hero__Human__friends'>>,
        #              'typing.List[typing.Optional[Q__hero__Human__friends]]')}
        self.assertEqual(m["__typename"].python_type, 'typing.Literal["Human"]')
        self.assertEqual(m["friends"].python_type, "typing.List[typing.Optional[Q__hero__Human__friends]]")
        self.assertTrue(isinstance(m["friends"].graphql_type, GraphQLList))

    def test_is_scalar_type(self):
        parsed_query = get_parsed_query(
            """
            query Q {
                hero {
                    name
                    appearsIn
                }
            }
            """
        )

        r = renderer.Renderer()
        self.assertFalse(r.is_scalar_type(parsed_query.fields["hero"].type))
        self.assertTrue(r.is_scalar_type(parsed_query.fields["hero"].fields["name"].type))
        self.assertTrue(r.is_scalar_type(parsed_query.fields["hero"].fields["appearsIn"].type))

    def test_get_assign_field_str(self):
        parsed_query = get_parsed_query(
            """
            query Q {
                hero {
                    name
                    friends {
                        name
                    }
                }
            }
            """
        )

        converter = renderer.DefaultAssignConverter(None)
        r = renderer.Renderer()
        b = renderer.CodeChunk()
        assign = r.get_assign_field_str(b, "name", parsed_query.fields["hero"].fields["name"].type, converter)
        self.assertEqual(assign, "name")

        converter = renderer.ObjectAssignConverter(field_type_str="Friend", demangle=["__typename"])
        assign = r.get_assign_field_str(
            b, "friends", parsed_query.fields["hero"].fields["friends"].type, converter
        )
        self.assertEqual(
            assign,
            "[Friend(**demangle(friends__iter, ['__typename']))"
            " if friends__iter else None for friends__iter in friends]",
        )

    def test_render_class(self):
        parsed_query = get_parsed_query(
            """
            query Q {
                hero {
                    __typename
                    name
                    bestFriend {
                        name
                    }
                    friends {
                        __typename
                        ... on Human {
                            name
                        }
                        ... on Droid {
                            primaryFunction
                        }
                    }
                }
            }
            """
        )

        r = renderer.Renderer()
        b = renderer.CodeChunk()
        r.render_class(b, "Hero", parsed_query.fields["hero"], parsed_query)

        self.assertEqual(
            str(b).strip(),
            inspect.cleandoc(
                """
                @dataclass
                class Hero:
                    _typename: typing.Literal["Character", "Droid", "Human"]
                    bestFriend: typing.Optional[Q__hero__bestFriend]
                    friends: typing.List[typing.Optional[Q__hero__friends]]
                    name: str
                    def __init__(self, _typename, bestFriend, friends, name):
                        self._typename = _typename
                        self.bestFriend = Q__hero__bestFriend(**bestFriend) if bestFriend else None
                        __friends_map = {
                            "Human": Q__hero__friends__Human,
                            "Droid": Q__hero__friends__Droid,
                        }
                        self.friends = [__friends_map.get(friends__iter["__typename"], Q__hero__friends)(**demangle(friends__iter, ['__typename'])) if friends__iter else None for friends__iter in friends]
                        self.name = name
                """  # noqa
            ),
        )

    def test_type_to_string(self):
        parsed_query = get_parsed_query(
            """
            query Q {
                a(id: "id") {
                    id llll r
                }
            }
            """
        )

        r = renderer.Renderer()
        self.assertEqual(r.type_to_string(parsed_query.fields["a"].fields["id"].type), "str")
        self.assertEqual(
            r.type_to_string(parsed_query.fields["a"].fields["llll"].type),
            "typing.List[typing.List[typing.List[typing.List[typing.Optional[str]]]]]",
        )
        self.assertEqual(
            r.type_to_string(parsed_query.fields["a"].fields["r"].type), "typing.Optional[Q__a__r]"
        )

    def test_node_type_to_string(self):
        parsed_query = get_parsed_query(
            """
            query Q($id: ID!, $llll: [[[[String]]]]) {
                a(id: $id) {
                    id name
                }
                a2(llll: $llll) {
                    id name
                }
            }
            """
        )

        r = renderer.Renderer()
        self.assertEqual(r.type_node_to_string(parsed_query.variable_map["id"].type_node), "str")
        self.assertEqual(
            r.type_node_to_string(parsed_query.variable_map["llll"].type_node),
            "typing.List[typing.List[typing.List[typing.List[typing.Optional[str]]]]]",
        )

    def test_render_variable_type(self):
        parsed_query = get_parsed_query(
            """
            query Q($id: ID!, $llll: [[[[String]]]]) {
                a(id: $id) {
                    id name
                }
                a2(llll: $llll) {
                    id name
                }
            }
            """
        )

        r = renderer.Renderer()
        b = renderer.CodeChunk()
        r.render_variable_type(b, "V", parsed_query.variable_map)

        self.assertEqual(
            str(b).strip(),
            inspect.cleandoc(
                """
                V__required = typing.TypedDict("V__required", {"id": str})
                V__not_required = typing.TypedDict("V__not_required", {"llll": typing.List[typing.List[typing.List[typing.List[typing.Optional[str]]]]]}, total=False)


                class V(V__required, V__not_required):
                    pass


                def V__serialize(data):
                    ret = copy.copy(data)
                    return ret
                """  # noqa
            ),
        )
