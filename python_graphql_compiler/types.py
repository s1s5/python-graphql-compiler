# pylint: disable=inherit-non-class, duplicate-bases

from typing import Dict, List, TypedDict

ScalarConfig__required = TypedDict("ScalarConfig__required", {"python_type": str})
ScalarConfig__not_required = TypedDict(
    "ScalarConfig__not_required", {"import": str, "serializer": str, "deserializer": str}, total=False
)


class ScalarConfig(ScalarConfig__required, ScalarConfig__not_required):
    pass


InheritConfig__required = TypedDict("InheritConfig__required", {"inherit": str})
InheritConfig__not_required = TypedDict("InheritConfig__not_required", {"import": str})


class InheritConfig(InheritConfig__required, InheritConfig__not_required):
    pass


class Config(TypedDict, total=True):
    output_path: str
    scalar_map: Dict[str, ScalarConfig]
    query_ext: str
    inherit: List[InheritConfig]
