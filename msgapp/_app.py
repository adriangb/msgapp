import inspect
from logging import getLogger
from typing import Any, AsyncContextManager, Awaitable, Callable, TypeVar, Union

from msgapp._executor import ExecutorFactory, concurrent_executor
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
        executor: ExecutorFactory = concurrent_executor(concurrency=1),
        raise_exceptions: bool = False,
    ) -> None:
        self._handler = handler
        self._parser = parser
        self._producer = producer
        self._executor = executor
        self._raise_exceptions = raise_exceptions

    async def run(self) -> None:
        handler: Callable[[MessageCM], Awaitable[None]]
        sig = inspect.signature(self._handler)
        if len(sig.parameters) not in (1, 2):
            raise TypeError
        model_type = next(iter(sig.parameters.values())).annotation
        parser = self._parser.create_parser(model_type)
        if len(sig.parameters) == 1:

            async def _handler(message_cm: MessageCM) -> None:
                try:
                    async with message_cm as message:
                        body = parser.parse(message.body)
                        await self._handler(body)  # type: ignore
                except Exception:
                    logger.exception("Uncaught exception in handler")
                    if self._raise_exceptions:
                        raise

            handler = _handler
        else:

            async def _handler(message_cm: MessageCM) -> None:
                try:
                    async with message_cm as message:
                        body = parser.parse(message.body)
                        await self._handler(body, message)  # type: ignore
                except Exception:
                    logger.exception("Uncaught exception in handler")
                    if self._raise_exceptions:
                        raise

            handler = _handler

        async with self._executor(handler) as executor:
            async for message_cm in self._producer.pull():
                await executor(message_cm)  # type: ignore
