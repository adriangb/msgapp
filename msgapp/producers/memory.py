from contextlib import asynccontextmanager
from typing import AsyncContextManager, AsyncIterable, AsyncIterator

from msgapp._producer import WrappedEnvelope


class InMemoryEventWrapper:
    def __init__(self, message: bytes) -> None:
        self.message = message

    @property
    def body(self) -> bytes:
        return self.message


class InMemoryQueue:
    def __init__(self, source: AsyncIterable[bytes]) -> None:
        self._source = source

    async def pull(self) -> AsyncIterable[AsyncContextManager[WrappedEnvelope[bytes]]]:
        async for event in self._source:

            @asynccontextmanager
            async def cm(
                event: "WrappedEnvelope[bytes]" = InMemoryEventWrapper(event),
            ) -> "AsyncIterator[WrappedEnvelope[bytes]]":
                yield event

            yield cm()
