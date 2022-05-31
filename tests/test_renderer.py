import inspect
import unittest

from typing import Optional

from graphql import GraphQLList, OperationDefinitionNode, build_ast_schema, parse

from python_graphql_compiler import renderer
from python_graphql_compiler.parser import ParsedQuery, Parser


def get_parsed_query(query_str: str, schema_str: Optional[str] = None) -> ParsedQuery:
    if schema_str is None:
        schema_str = """
        scalar MyScalar
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
        input ComplexInput {
            a: [[AddInput]]!
            b: [[SubInput!]] = []
            c: MyScalar
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
            a3(llll: [[[[SubInput]]]]): A
            a4(x: String): String
            a5(x: MyScalar!): String
            a6(x: MyScalar): String
            a70(x: [MyScalar]): String
            a71(x: [MyScalar!]): String
            a72(x: [MyScalar]!): String
            a73(x: [MyScalar!]!): String
            b(a: AddInput!): String!
            hero: Character
        }
        type Mutation {
            add(input: AddInput!): A
            runComplex(input: ComplexInput!): A
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
    maxDiff = None

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
            query Q($input: AddInput!) {
                b(a: $input)
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

        r = renderer.Renderer(inherit=[{"import": "import", "inherit": "Hoge"}])
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
                    if "sub" in data:
                        x = data["sub"]
                        ret["sub"] = AddInput__serialize(x) if x else None
                    return ret
                """  # noqa
            ),
        )

    def test_render_input_complex(self):
        parsed_query = get_parsed_query(
            """
            mutation M($input: ComplexInput!) {
                runComplex(input: $input) {
                    name
                }
            }
            """
        )
        b = renderer.CodeChunk()
        r = renderer.Renderer(
            scalar_map={
                "MyScalar": {
                    "serializer": "MyScalar.serialize({value})",
                    "python_type": "MyScalar",
                }
            }
        )
        r.render_input(b, "SubInput", parsed_query.used_input_types["SubInput"])
        r.render_input(b, "AddInput", parsed_query.used_input_types["AddInput"])
        r.render_input(b, "ComplexInput", parsed_query.used_input_types["ComplexInput"])

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
            if "sub" in data:
                x = data["sub"]
                ret["sub"] = AddInput__serialize(x) if x else None
            return ret


        ComplexInput__required = typing.TypedDict("ComplexInput__required", {"a": typing.List[typing.List[typing.Optional[AddInput]]]})
        ComplexInput__not_required = typing.TypedDict("ComplexInput__not_required", {"b": typing.List[typing.List[SubInput]], "c": typing.Optional[MyScalar]}, total=False)


        class ComplexInput(ComplexInput__required, ComplexInput__not_required):
            pass


        def ComplexInput__serialize(data):
            ret = copy.copy(data)
            x = data["a"]
            ret["a"] = [[ComplexInput__serialize(x__iter__iter) if x__iter__iter else None for x__iter__iter in x__iter] for x__iter in x]
            if "b" in data:
                x = data["b"]
                ret["b"] = [[ComplexInput__serialize(x__iter__iter) for x__iter__iter in x__iter] for x__iter in x]
            if "c" in data:
                x = data["c"]
                ret["c"] = MyScalar.serialize(x) if x else None
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

    def test_render_class_union(self):
        parsed_query = get_parsed_query(
            """
            query Q {
                a(id: "foo") {
                    r {
                        __typename
                        ... on Human {
                            name
                        }
                        ... on Droid {
                            primaryFunction
                        }
                        ... on Starship {
                            name
                        }
                    }
                }
            }
            """
        )

        r = renderer.Renderer()
        b = renderer.CodeChunk()
        r.render_all_classes(b, [parsed_query], set())
        b = renderer.CodeChunk()
        # r.render([parsed_query])
        # r.render_class(b, "Hero", parsed_query.fields["hero"], parsed_query)
        r.render_class(b, "Q__a", parsed_query.type_map["Q__a"], parsed_query)
        # for class_name, class_info in reversed(parsed_query.type_map.items()):
        #     b.write("")
        #     b.write("")
        #     r.render_class(b, class_name, class_info, parsed_query)
        # print(str(b).strip())
        self.assertEqual(
            str(b).strip(),
            inspect.cleandoc(
                """
                @dataclass
                class Q__a:
                    r: typing.Optional[Q__a__r | Q__a__r__Human | Q__a__r__Droid | Q__a__r__Starship]
                    def __init__(self, r):
                        __r_map = {
                            "Human": Q__a__r__Human,
                            "Droid": Q__a__r__Droid,
                            "Starship": Q__a__r__Starship,
                        }
                        self.r = __r_map.get(r["__typename"], Q__a__r)(**demangle(r, ['__typename'])) if r else None
            """  # noqa
            ),
        )

        b = renderer.CodeChunk()
        r.python_version = (3, 8)
        r.render_class(b, "Q__a", parsed_query.type_map["Q__a"], parsed_query)
        self.assertEqual(
            str(b).strip(),
            inspect.cleandoc(
                """
                @dataclass
                class Q__a:
                    r: typing.Optional[typing.Union[Q__a__r, Q__a__r__Human, Q__a__r__Droid, Q__a__r__Starship]]
                    def __init__(self, r):
                        __r_map = {
                            "Human": Q__a__r__Human,
                            "Droid": Q__a__r__Droid,
                            "Starship": Q__a__r__Starship,
                        }
                        self.r = __r_map.get(r["__typename"], Q__a__r)(**demangle(r, ['__typename'])) if r else None
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
            query Q($id: ID!, $llll: [[[[String]]]], $v3: [[[[SubInput]]]], $v4: String, $v5: MyScalar!, $v6: MyScalar, $v70: [MyScalar], $v71: [MyScalar!], $v72: [MyScalar]!, $v73: [MyScalar!]!) {
                a(id: $id) {
                    id name
                }
                a2(llll: $llll) {
                    id name
                }
                a3(llll: $v3) {
                    name
                }
                a4(x: $v4)
                a5(x: $v5)
                a6(x: $v6)
                a70(x: $v70)
                a71(x: $v71)
                a72(x: $v72)
                a73(x: $v73)
            }
            """  # noqa
        )

        r = renderer.Renderer(
            scalar_map={
                "MyScalar": {
                    "serializer": "MyScalar.serialize({value})",
                    "python_type": "MyScalar",
                }
            }
        )
        b = renderer.CodeChunk()
        r.render_variable_type(b, "V", parsed_query.variable_map)

        self.assertEqual(
            str(b).strip(),
            inspect.cleandoc(
                """
                V__required = typing.TypedDict("V__required", {"id": str, "v5": MyScalar, "v72": typing.List[typing.Optional[MyScalar]], "v73": typing.List[MyScalar]})
                V__not_required = typing.TypedDict("V__not_required", {"llll": typing.List[typing.List[typing.List[typing.List[typing.Optional[str]]]]], "v3": typing.List[typing.List[typing.List[typing.List[typing.Optional[SubInput]]]]], "v4": typing.Optional[str], "v6": typing.Optional[MyScalar], "v70": typing.List[typing.Optional[MyScalar]], "v71": typing.List[MyScalar]}, total=False)


                class V(V__required, V__not_required):
                    pass


                def V__serialize(data):
                    ret = copy.copy(data)
                    if v3 in data:
                        x = data["v3"]
                        ret["v3"] = [[[[SubInput__serialize(x__iter__iter__iter__iter) if x__iter__iter__iter__iter else None for x__iter__iter__iter__iter in x__iter__iter__iter] for x__iter__iter__iter in x__iter__iter] for x__iter__iter in x__iter] for x__iter in x]
                    x = data["v5"]
                    ret["v5"] = MyScalar.serialize(x)
                    if v6 in data:
                        x = data["v6"]
                        ret["v6"] = MyScalar.serialize(x) if x else None
                    if v70 in data:
                        x = data["v70"]
                        ret["v70"] = [MyScalar.serialize(x__iter) if x__iter else None for x__iter in x]
                    if v71 in data:
                        x = data["v71"]
                        ret["v71"] = [MyScalar.serialize(x__iter) for x__iter in x]
                    x = data["v72"]
                    ret["v72"] = [MyScalar.serialize(x__iter) if x__iter else None for x__iter in x]
                    x = data["v73"]
                    ret["v73"] = [MyScalar.serialize(x__iter) for x__iter in x]
                    return ret
                """  # noqa
            ),
        )
