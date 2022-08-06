from typing import AsyncIterable, Optional

import anyio
import pytest
from pydantic import BaseModel

from msgapp import App, concurrent_executor
from msgapp.parsers.json import PydanticParserFactory
from msgapp.producers.memory import InMemoryQueue


class MyModel(BaseModel):
    foo: str
    baz: int


@pytest.mark.anyio
@pytest.mark.parametrize(
    "concurrency,expected_concurrency",
    [
        (None, 3),
        (1, 1),
        (2, 2),
    ],
)
async def test_concurrency(
    concurrency: Optional[int], expected_concurrency: int
) -> None:
    async def source() -> AsyncIterable[bytes]:
        yield b'{"foo": "bar", "baz": 1}'
        yield b'{"foo": "bar", "baz": 1}'
        yield b'{"foo": "bar", "baz": 1}'

    tokens = 0
    max_tokens = 0

    async def handler(_: MyModel) -> None:
        nonlocal tokens, max_tokens
        tokens += 1
        max_tokens = max(tokens, max_tokens)
        await anyio.sleep(0.1)
        tokens -= 1

    app = App(
        handler,
        producer=InMemoryQueue(source()),
        parser=PydanticParserFactory(),
        executor=concurrent_executor(concurrency=concurrency),
    )

    await app.run()

    assert max_tokens == expected_concurrency
