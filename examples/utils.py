"utility"
import json

from typing import Protocol, TypeVar

import aiohttp
import requests

V_contra = TypeVar("V_contra", contravariant=True)
R_co = TypeVar("R_co", covariant=True)


class Client(Protocol[V_contra, R_co]):
    "requests client"

    @classmethod
    def serialize(cls, variables: V_contra):
        ...

    @classmethod
    def deserialize(cls, data) -> R_co:
        ...

    @classmethod
    def execute(cls, endpoint: str, variables: V_contra) -> R_co:
        "execute graphql query"
        res = requests.post(endpoint, json=cls.serialize(variables))
        res.raise_for_status()
        res_json = res.json()
        assert res_json.get("error") is None
        return cls.deserialize(res_json["data"])

    @classmethod
    async def execute_async(cls, endpoint: str, variables: V_contra) -> R_co:
        "execute graphql query async"
        async with aiohttp.ClientSession(headers={"Content-Type": "application/json"}) as session:
            async with session.post(url=endpoint, data=json.dumps(cls.serialize(variables))) as response:
                res_json = await response.json(content_type=None)
                assert res_json.get("error") is None
                return cls.deserialize(res_json["data"])
