# pylint: disable=inherit-non-class, duplicate-bases

from typing import Dict, List, Literal, TypedDict, Union

ScalarConfig__required = TypedDict("ScalarConfig__required", {"python_type": str})
ScalarConfig__not_required = TypedDict(
    "ScalarConfig__not_required",
    {"import": Union[str, List[str]], "serializer": str, "deserializer": str},
    total=False,
)


class ScalarConfig(ScalarConfig__required, ScalarConfig__not_required):
    pass


InheritConfig__required = TypedDict("InheritConfig__required", {"inherit": str})
InheritConfig__not_required = TypedDict("InheritConfig__not_required", {"import": Union[str, List[str]]})


class InheritConfig(InheritConfig__required, InheritConfig__not_required):
    pass


class Config(TypedDict, total=True):
    output_path: str
    scalar_map: Dict[str, ScalarConfig]
    query_ext: str
    inherit: List[InheritConfig]
    python_version: Literal["3.8", "3.9", "3.10"]
