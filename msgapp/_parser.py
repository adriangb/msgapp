import sys
from typing import Type, TypeVar

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

BodyType = TypeVar("BodyType")
BodyTypeCO = TypeVar("BodyTypeCO", covariant=True)


class BodyParser(Protocol[BodyTypeCO]):
    def parse(self, __body: bytes) -> BodyTypeCO:
        ...


class BodyParserFactory(Protocol[BodyType]):
    def create_parser(self, __model: Type[BodyType]) -> BodyParser[BodyType]:
        ...
