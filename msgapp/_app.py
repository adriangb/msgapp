import inspect
from logging import getLogger
from typing import Any, AsyncContextManager, Awaitable, Callable, TypeVar, Union

import anyio

from msgapp._parser import BodyParserFactory
from msgapp._producer import Producer, WrappedEnvelope

BodyType = TypeVar("BodyType")
MessageType = TypeVar("MessageType")
MessageCM = AsyncContextManager[WrappedEnvelope[Any]]


Handler = Union[
    Callable[[BodyType, WrappedEnvelope[MessageType]], Awaitable[None]],
    Callable[[BodyType], Awaitable[None]],
]


logger = getLogger(__name__)


class App:
    def __init__(
        self,
        handler: Handler[BodyType, MessageType],
        *,
        parser: BodyParserFactory[BodyType],
        producer: Producer[MessageType],
        concurrency: int = 1,
        raise_exceptions: bool = False,
    ) -> None:
        self._handler = handler
        self._parser = parser
        self._producer = producer
        self._concurrency = concurrency
        self._raise_exceptions = raise_exceptions

    async def run(self) -> None:
        handler: Callable[[WrappedEnvelope[Any]], Awaitable[None]]
        sig = inspect.signature(self._handler)
        send, rcv = anyio.create_memory_object_stream(0, item_type=MessageCM)
        if len(sig.parameters) not in (1, 2):
            raise TypeError
        model_type = next(iter(sig.parameters.values())).annotation
        parser = self._parser.create_parser(model_type)
        if len(sig.parameters) == 1:

            async def _handler(message: WrappedEnvelope[Any]) -> None:
                body = parser.parse(message.body)
                await self._handler(body)  # type: ignore

            handler = _handler
        else:

            async def _handler(message: WrappedEnvelope[Any]) -> None:
                body = parser.parse(message.body)
                await self._handler(body, message)  # type: ignore

            handler = _handler

        async def worker() -> None:
            async for message_cm in rcv:
                async with message_cm as message:
                    try:
                        await handler(message)
                    except Exception:
                        logger.exception("Uncaught exception in handler")
                        if self._raise_exceptions:
                            raise

        async with anyio.create_task_group() as tg:
            for _ in range(self._concurrency):
                tg.start_soon(worker)
            async with send:
                async for message_cm in self._producer.pull():
                    await send.send(message_cm)
