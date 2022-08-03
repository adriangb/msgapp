from typing import Protocol, Type, TypeVar

BodyType = TypeVar("BodyType")
BodyTypeCO = TypeVar("BodyTypeCO", covariant=True)


class BodyParser(Protocol[BodyTypeCO]):
    def parse(self, __body: bytes) -> BodyTypeCO:
        ...


class BodyParserFactory(Protocol[BodyType]):
    def create_parser(self, __model: Type[BodyType]) -> BodyParser[BodyType]:
        ...
