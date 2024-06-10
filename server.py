import asyncio
import logging
from os import getenv
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from redis import asyncio as aredis


class StateManager:
    def __init__(self, name, state):
        self.name = name
        self.state = state
        self._clients: set[WebSocket] = set()
        self._logger = logging.getLogger("state")

    async def add(self, client: WebSocket):
        await client.accept()
        self._clients.add(client)

    def remove(self, client: WebSocket):
        self._clients.remove(client)

    async def _pubsub_listener(self) -> None:
        async for message in self._pubsub.listen():
            self._logger.info(message)
            # {'type': 'message', 'pattern': None, 'channel': b'color', 'data': b'#123456'}
            if message["type"] == "message":
                try:
                    state = message["data"].decode()
                    self.state = state
                    if self._clients:
                        # websockets.broadcast(self._clients, state)
                        for client in self._clients:
                            await client.send_text(state)
                except Exception as e:
                    self._logger.exception(e)

    async def setup(self, redis_url) -> None:
        self._conn = aredis.Redis.from_url(redis_url)
        self._pubsub = self._conn.pubsub(ignore_subscribe_messages=True)
        await self._pubsub.subscribe(self.name)
        self._listener = asyncio.create_task(self._pubsub_listener())

    async def teardown(self) -> None:
        await self._pubsub.aclose()
        await self._conn.aclose()
        self._listener.cancel()

    async def publish(self, message) -> None:
        self._logger.debug(self._listener)
        delivered = await self._conn.publish(self.name, message)
        self._logger.info("message=%s delivered=%s", message, delivered)


async def get_manager():
    manager = StateManager("color", "#abcdef")
    await manager.setup(getenv("REDIS", "redis://localhost/0"))
    yield manager
    await manager.teardown()


app = FastAPI(debug=bool(getenv("DEBUG")), docs_url=None, redoc_url=None)


@app.websocket("/")
async def websocket_color(
    client: WebSocket,
    manager: Annotated[StateManager, Depends(get_manager)],
):
    await manager.add(client)
    try:
        await client.send_text(manager.state)
        while True:
            text = await client.receive_text()
            await manager.publish(text)
    except WebSocketDisconnect:
        manager.remove(client)
    except Exception as e:
        logging.exception(e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG if getenv("DEBUG") else logging.INFO)
    uvicorn.run(app, host=getenv("HOST", "localhost"), port=int(getenv("PORT", "5000")))
