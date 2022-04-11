# pylint: disable=import-outside-toplevel, missing-function-docstring
"""test function"""

import pytest

ENDPOINT = "http://localhost:8000"


def test_get_scalar():
    from queries import GetScalar

    result = GetScalar.execute(ENDPOINT, {})
    assert result == GetScalar.Response(hello="hello world")


def test_get_inline_fragment():
    from queries import GetInlineFragment

    result = GetInlineFragment.execute(ENDPOINT, {"e": "JEDI"})
    assert result == GetInlineFragment.Response(
        hero=dict(__typename="Droid", id="d-1", name="C-3PO", primaryFunction="search")
    )


@pytest.mark.asyncio
async def test_get_scalar_async():
    from queries import GetScalar

    result = await GetScalar.execute_async(ENDPOINT, {})
    assert result == GetScalar.Response(hello="hello world")
