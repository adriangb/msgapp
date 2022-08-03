from typing import Any, AsyncIterable, List

import pytest
from pydantic import BaseModel

from msgapp import App, WrappedEnvelope
from msgapp.parsers.json import PydanticParserFactory
from msgapp.producers.memory import InMemoryQueue


class MyModel(BaseModel):
    foo: str
    baz: int


@pytest.mark.anyio
async def test_consume_messages() -> None:
    async def source() -> AsyncIterable[bytes]:
        yield b'{"foo": "bar", "baz": 1}'

    received: List[Any] = []

    async def handler(message: MyModel) -> None:
        received.append(message)

    app = App(
        handler,
        producer=InMemoryQueue(source()),
        parser=PydanticParserFactory(),
    )

    await app.run()

    assert received == [MyModel(foo="bar", baz=1)]


@pytest.mark.anyio
async def test_consume_messages_raw() -> None:
    async def source() -> AsyncIterable[bytes]:
        yield b'{"foo": "bar", "baz": 1}'

    received: List[Any] = []

    async def handler(message: MyModel, event: WrappedEnvelope[bytes]) -> None:
        received.append((message, event.body, event.message))

    app = App(
        handler,
        producer=InMemoryQueue(source()),
        parser=PydanticParserFactory(),
    )

    await app.run()

    assert received == [
        (
            MyModel(foo="bar", baz=1),
            b'{"foo": "bar", "baz": 1}',
            b'{"foo": "bar", "baz": 1}',
        )
    ]


@pytest.mark.anyio
async def test_raise_exceptions_true() -> None:
    async def source() -> AsyncIterable[bytes]:
        yield b'{"foo": "bar", "baz": 1}'

    class MyException(Exception):
        pass

    async def handler(message: MyModel) -> None:
        raise MyException

    app = App(
        handler,
        producer=InMemoryQueue(source()),
        parser=PydanticParserFactory(),
        raise_exceptions=True,
    )

    with pytest.raises(MyException):
        await app.run()


@pytest.mark.anyio
async def test_raise_exceptions_false() -> None:
    async def source() -> AsyncIterable[bytes]:
        yield b'{"foo": "bar", "baz": 1}'

    class MyException(Exception):
        pass

    async def handler(message: MyModel) -> None:
        raise MyException

    app = App(
        handler,
        producer=InMemoryQueue(source()),
        parser=PydanticParserFactory(),
        raise_exceptions=False,
    )

    await app.run()
