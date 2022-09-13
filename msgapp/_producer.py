import sys
from typing import AsyncContextManager, AsyncIterable, TypeVar

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

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
