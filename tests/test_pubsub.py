import os
from contextlib import asynccontextmanager
from random import randint
from typing import Any, AsyncIterable, AsyncIterator, List
from unittest.mock import patch
from uuid import uuid4

import anyio
import anyio.abc
import anyio.to_process
import pytest
from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials  # type: ignore
from google.cloud.pubsub import PublisherClient  # type: ignore
from google.pubsub import SubscriberAsyncClient
from pydantic import BaseModel

from msgapp import App
from msgapp.parsers.json import PydanticParserFactory
from msgapp.producers.pubsub import PubSubQueue


class MyModel(BaseModel):
    foo: str
    baz: int


@pytest.fixture(
    params=[
        pytest.param(("asyncio", {"use_uvloop": False}), id="asyncio"),
    ],
    scope="session",
)
def anyio_backend(request: Any) -> Any:
    return request.param


@pytest.fixture(scope="session")
@pytest.mark.anyio
async def pubsub_emulator_endpoint() -> AsyncIterable[str]:
    port = randint(8000, 9000)
    cmd = f"gcloud beta emulators pubsub start --project=test --host-port=localhost:{port}"

    @asynccontextmanager
    async def run_emulator() -> AsyncIterator[None]:
        p = await anyio.open_process(cmd)
        stdout = p.stdout
        assert stdout is not None
        stderr = p.stderr
        assert stderr is not None
        resp = bytearray()
        try:
            with anyio.fail_after(30):
                while b"Server started" not in resp:
                    resp.extend(await stderr.receive())
        except TimeoutError:
            print(resp.decode())
            raise
        try:
            yield
        finally:
            p.terminate()
            await p.wait()

    endpoint = f"127.0.0.1:{port}"

    async with run_emulator():
        with patch.dict(os.environ, values={"PUBSUB_EMULATOR_HOST": endpoint}):
            yield endpoint


@pytest.fixture
def publisher_client(pubsub_emulator_endpoint: str) -> PublisherClient:
    client_options = ClientOptions(api_endpoint=pubsub_emulator_endpoint)  # type: ignore[no-untyped-call]
    return PublisherClient(
        client_options=client_options,
        credentials=AnonymousCredentials(),
    )


@pytest.fixture
def topic(publisher_client: PublisherClient, pubsub_emulator_endpoint: str) -> str:
    topic = f"projects/test/topics/topic-{uuid4()}"
    publisher_client.create_topic(name=topic)  # type: ignore
    return topic


@pytest.fixture
async def subscriber_client(pubsub_emulator_endpoint: str) -> SubscriberAsyncClient:
    client_options = ClientOptions(api_endpoint=pubsub_emulator_endpoint)  # type: ignore[no-untyped-call]
    subscriber = SubscriberAsyncClient(
        client_options=client_options,
        credentials=AnonymousCredentials(),
    )
    return subscriber


@pytest.fixture
async def subscription(
    subscriber_client: SubscriberAsyncClient,
    topic: str,
) -> str:
    subscription = f"projects/test/subscriptions/sub-{uuid4()}"
    await subscriber_client.create_subscription(  # type: ignore
        name=subscription,
        topic=topic,
    )
    return subscription


@pytest.mark.anyio
async def test_consume_messages(
    subscription: str,
    topic: str,
    subscriber_client: SubscriberAsyncClient,
    publisher_client: PublisherClient,
) -> None:
    received: List[Any] = []

    done = anyio.Event()

    async def handler(message: MyModel) -> None:
        received.append(message)
        done.set()

    app = App(
        handler,
        producer=PubSubQueue(subscription=subscription, client=subscriber_client),
        parser=PydanticParserFactory(),
    )

    async with anyio.create_task_group() as tg:
        tg.start_soon(app.run)
        publisher_client.publish(  # type: ignore
            topic=topic,
            data=b'{"foo": "bar", "baz": 1}',
        )
        await done.wait()
        tg.cancel_scope.cancel()

    assert received == [MyModel(foo="bar", baz=1)]
