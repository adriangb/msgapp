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
