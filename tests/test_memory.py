from typing import Any, AsyncIterable, List

import anyio
import pytest
from pydantic import BaseModel

from msgapp import App, WrappedEnvelope
from msgapp.parsers.json import PydanticParserFactory
from msgapp.producers.memory import InMemoryQueue


class MyModel(BaseModel):
    foo: str
    baz: int


@pytest.mark.anyio
async def test_consume_messages_generator() -> None:
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
async def test_consume_messages_queue() -> None:
    send, rcv = anyio.create_memory_object_stream(0, item_type=bytes)

    received: List[Any] = []

    async def handler(message: MyModel) -> None:
        received.append(message)

    app = App(
        handler,
        producer=InMemoryQueue(rcv),
        parser=PydanticParserFactory(),
    )

    async with rcv:
        async with send:
            async with anyio.create_task_group() as tg:
                tg.start_soon(app.run)
                async with send:
                    await send.send(b'{"foo": "bar", "baz": 1}')

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
