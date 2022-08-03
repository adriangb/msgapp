from typing import AsyncContextManager, AsyncIterable, Protocol, TypeVar

EnvelopeType = TypeVar("EnvelopeType", covariant=True)


class WrappedEnvelope(Protocol[EnvelopeType]):
    @property
    def body(self) -> bytes:
        ...

    @property
    def message(self) -> EnvelopeType:
        ...


class Producer(Protocol[EnvelopeType]):
    def pull(self) -> AsyncIterable[AsyncContextManager[WrappedEnvelope[EnvelopeType]]]:
        ...
