from contextlib import asynccontextmanager
from functools import partial
from typing import (
    AsyncContextManager,
    AsyncIterator,
    Awaitable,
    Callable,
    Coroutine,
    NewType,
    Optional,
)

import anyio

from msgapp._producer import WrappedEnvelope

BodyType = NewType("BodyType", object)
MessageType = NewType("MessageType", object)
WrappedMessage = WrappedEnvelope[MessageType]
WrappedMessageCM = AsyncContextManager[WrappedMessage]

Handler = Callable[[WrappedMessageCM], Coroutine[None, None, None]]
Executor = Callable[[WrappedMessageCM], Awaitable[None]]
ExecutorFactory = Callable[[Handler], AsyncContextManager[Executor]]


@asynccontextmanager
async def _unbound_executor(handler: Handler) -> AsyncIterator[Executor]:
    async with anyio.create_task_group() as tg:

        async def exec(message: WrappedMessageCM) -> None:
            tg.start_soon(handler, message)

        yield exec


@asynccontextmanager
async def _sequential_executor(handler: Handler) -> AsyncIterator[Executor]:
    yield handler


@asynccontextmanager
async def _bound_executor(
    handler: Handler, concurrency: int
) -> AsyncIterator[Executor]:
    send, rcv = anyio.create_memory_object_stream(concurrency, WrappedMessageCM)  # type: ignore[misc]
    async with anyio.create_task_group() as tg, send:

        async def worker() -> None:
            async for message in rcv:
                await handler(message)

        for _ in range(concurrency):
            tg.start_soon(worker)
        yield send.send


def concurrent_executor(concurrency: Optional[int]) -> ExecutorFactory:
    if concurrency is None:
        return _unbound_executor
    elif concurrency == 1:
        return _sequential_executor
    return partial(_bound_executor, concurrency=concurrency)
