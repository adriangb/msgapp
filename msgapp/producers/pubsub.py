from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from logging import getLogger
from math import floor
from typing import (
    Any,
    AsyncContextManager,
    AsyncIterable,
    AsyncIterator,
    Mapping,
    Optional,
    cast,
)

import anyio
from google.pubsub import ReceivedMessage, StreamingPullRequest, SubscriberAsyncClient

from msgapp._producer import Producer, WrappedEnvelope

logger = getLogger(__name__)


@dataclass
class PubSubMessage:
    data: bytes
    attributes: Mapping[str, Any]
    message_id: str
    publish_time: datetime
    ordering_key: str


class WrappedPubSubEvent:
    def __init__(self, message: PubSubMessage) -> None:
        self.message = message

    @property
    def body(self) -> bytes:
        return self.message.data


class PubSubQueue(Producer[PubSubMessage]):
    def __init__(
        self,
        subscription: str,
        *,
        client: Optional[SubscriberAsyncClient] = None,
    ) -> None:
        self._client = client or SubscriberAsyncClient()  # type: ignore
        self._subscription = subscription

    async def pull(
        self,
    ) -> AsyncIterable[AsyncContextManager[WrappedEnvelope[PubSubMessage]]]:
        subscription = await self._client.get_subscription(subscription=self._subscription)  # type: ignore
        subscription_ack_deadline = cast(int, subscription.ack_deadline_seconds)

        def clip(n: int, lo: int, hi: int) -> int:
            return min(max(n, lo), hi)

        # use 1/2 of whatever the deadline is or at least 1 second
        # the min deadline is 10 seconds and max is 600 seconds
        ack_check_in_interval = clip(floor(subscription_ack_deadline / 2), 1, 300)

        async def request_generator() -> AsyncIterator[StreamingPullRequest]:
            yield StreamingPullRequest(
                subscription=self._subscription,
                stream_ack_deadline_seconds=subscription_ack_deadline,
            )
            while True:
                yield StreamingPullRequest()

        async for events in await self._client.streaming_pull(  # type: ignore
            requests=request_generator()
        ):
            for event in events.received_messages:  # type: ignore
                event = cast(ReceivedMessage, event)

                msg = event.message

                wrapped = WrappedPubSubEvent(
                    PubSubMessage(
                        data=msg.data,  # type: ignore
                        attributes=msg.attributes,  # type: ignore
                        message_id=msg.message_id,  # type: ignore
                        publish_time=msg.publish_time,  # type: ignore
                        ordering_key=msg.ordering_key,  # type: ignore
                    )
                )

                @asynccontextmanager
                async def cm(
                    wrapped: WrappedPubSubEvent = wrapped,
                ) -> "AsyncIterator[WrappedPubSubEvent]":
                    try:
                        async with anyio.create_task_group() as tg:

                            async def extend_ack() -> None:
                                await self._client.modify_ack_deadline(  # type: ignore
                                    ack_ids=(event.ack_id,),  # type: ignore
                                    ack_deadline_seconds=subscription_ack_deadline,
                                )
                                await anyio.sleep(ack_check_in_interval)
                                tg.start_soon(extend_ack)

                            tg.start_soon(extend_ack)
                            yield wrapped
                            tg.cancel_scope.cancel()
                            await self._client.acknowledge(ack_ids=(event.ack_id,))  # type: ignore
                    except Exception:
                        # try to put the message back on the queue
                        await self._client.modify_ack_deadline(  # type: ignore
                            ack_ids=(event.ack_id,),  # type: ignore
                            ack_deadline_seconds=10,  # min deadline
                        )
                        logger.exception("Unhandled exception processing message")
                        raise

                yield cm()
