# msgapp: declarative message driven applications

`msgapp` helps you write event consuming applications with minimal boilerplate.
It abstracts away some of the fiddly details of dealing with messaging queues like acks, deadlines and parsing.
The design is focused on flexibility and testability, offering the ability to swap out event backends (currently only PubSub) and support multiple parsers (only JSON via Pydantic is supplied out of the box for now).

## Examples

### Pydantic + PubSub

```python
import anyio
from pydantic import BaseModel
from msgapp import App
from msgapp.producers.pubsub import PubSubQueue
from msgapp.parsers.json import PydanticParserFactory

class MyModel(BaseModel):
    foo: str
    baz: int

async def handler(model: MyModel) -> None:
    # do something with the model
    print(model)
    # return to ack/consume the model
    # raise an exception to signal an error
    # and let the queue handle redelivery

app = App(
    handler,
    producer=PubSubQueue(subscription="projects/demo/subscriptions/foo-bar"),
    parser=PydanticParserFactory(),
)

anyio.run(app.run)
```

### Redis Streams + Pydantic

We do not include a Redis implementation simply because there are many ways that redis can be used for messaging. For example, you may use Redis' PubSub functionality for fire and forget messaging or Streams for reliable Kafka-like operation.

Below is an example implementation using Redis streams.
While this may not be exactly the implementation you want, it should give you some idea of how to write a Redis producer.

```python
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import (
    Any,
    AsyncContextManager,
    AsyncIterator,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from msgapp._producer import Producer


@dataclass(frozen=True)
class RedisMessage:
    payload: Mapping[bytes, bytes]
    id: bytes


class RedisWrappedEnvelope:
    def __init__(self, message: RedisMessage, body: bytes) -> None:
        self._message = message
        self._body = body

    @property
    def body(self) -> bytes:
        return self._body

    @property
    def message(self) -> RedisMessage:
        return self._message


class RedisProducer(Producer[Any]):
    def __init__(
        self,
        client: "Redis[Any]",
        stream: str,
        group: str,
        message_key: bytes,
        consumer_name: str,
        batch_size: int = 10,
        poll_interval: int = 30,
    ) -> None:
        self._client = client
        self._stream = stream
        self._group = group
        self._batch_size = batch_size
        self._poll_interval = poll_interval
        self._message_key = message_key
        self._consumer_name = consumer_name

    async def pull(self) -> AsyncIterator[AsyncContextManager[RedisWrappedEnvelope]]:
        try:
            await self._client.xgroup_create(
                name=self._stream, groupname=self._group, mkstream=True
            )
        except ResponseError as e:
            if "Consumer Group name already exists" in e.args[0]:
                pass
            else:
                raise
        last_id: Optional[bytes] = None
        items: Optional[
            Sequence[Tuple[str, Sequence[Tuple[bytes, Mapping[bytes, bytes]]]]]
        ] = None
        while True:
            items = await self._client.xreadgroup(
                groupname=self._group,
                consumername=self._consumer_name,
                streams={self._stream: last_id or ">"},
                block=1,
                count=1,
            )
            if not items:
                continue
            stream_items = next(iter(items))
            if len(stream_items[1]) == 0:
                last_id = None
                continue
            _, stream_messages = stream_items
            for message_id, values in stream_messages:
                last_id = message_id

                wrapped_msg = RedisMessage(payload=values, id=message_id)
                wrapped_envelope = RedisWrappedEnvelope(
                    wrapped_msg, values[self._message_key]
                )

                @asynccontextmanager
                async def msg_wrapper(
                    envelope: RedisWrappedEnvelope = wrapped_envelope,
                ) -> AsyncIterator[RedisWrappedEnvelope]:
                    yield envelope
                    await self._client.xack(  # type: ignore
                        self._stream, self._group, envelope.message.id
                    )

                yield msg_wrapper()


if __name__ == "__main__":
    import anyio
    from pydantic import BaseModel

    from msgapp import App
    from msgapp.parsers.json import PydanticParserFactory

    class MyModel(BaseModel):
        foo: str

    async def handler(message: MyModel) -> None:
        print(repr(message))

    stream = "mystream"  # str(uuid4())

    async def main() -> None:
        client = Redis.from_url("redis://localhost")
        producer = RedisProducer(client, stream, "mygroup", b"message", "consumer")

        app = App(handler, parser=PydanticParserFactory(), producer=producer)

        async with anyio.create_task_group() as tg:
            tg.start_soon(app.run)
            await client.xadd(stream, {b"message": b'{"foo": "bar"}'})
            await client.xadd(stream, {b"message": b'{"foo": "baz"}'})
            await anyio.sleep(1)
            tg.cancel_scope.cancel()

    anyio.run(main)
```
