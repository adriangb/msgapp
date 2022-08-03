from typing import Type, TypeVar

from pydantic import BaseModel

from msgapp._parser import BodyParser, BodyParserFactory

ModelType = TypeVar("ModelType", bound=BaseModel)


class PydanticParser(BodyParser[ModelType]):
    def __init__(self, model: Type[ModelType]) -> None:
        self.model = model

    def parse(self, __body: bytes) -> ModelType:
        return self.model.parse_raw(__body)


class PydanticParserFactory(BodyParserFactory[ModelType]):
    def create_parser(self, model: Type[ModelType]) -> BodyParser[ModelType]:
        return PydanticParser(model)
