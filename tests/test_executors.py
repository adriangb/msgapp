from typing import Any, AsyncIterable, List, Optional

import pytest
from pydantic import BaseModel

from msgapp import App, concurrent_executor
from msgapp.parsers.json import PydanticParserFactory
from msgapp.producers.memory import InMemoryQueue


class MyModel(BaseModel):
    foo: str
    baz: int


@pytest.mark.anyio
@pytest.mark.parametrize("concurrency", [None, 1, 2])
async def test_consume_messages(concurrency: Optional[int]) -> None:
    async def source() -> AsyncIterable[bytes]:
        yield b'{"foo": "bar", "baz": 1}'

    received: List[Any] = []

    async def handler(message: MyModel) -> None:
        received.append(message)

    app = App(
        handler,
        producer=InMemoryQueue(source()),
        parser=PydanticParserFactory(),
        executor=concurrent_executor(concurrency=concurrency),
    )

    await app.run()

    assert received == [MyModel(foo="bar", baz=1)]
