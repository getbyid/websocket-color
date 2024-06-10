import asyncio
import logging
import signal
from os import getenv

import websockets
from redis import asyncio as aredis


class StateManager:
    def __init__(self, name, state):
        self.name = name
        self.state = state
        self._clients = set()
        self._logger = logging.getLogger("state")

    def add(self, client):
        self._clients.add(client)

    def remove(self, client):
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
                        websockets.broadcast(self._clients, state)
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

    async def publish(self, state) -> None:
        self._logger.debug(self._listener)
        delivered = await self._conn.publish(self.name, state)
        self._logger.info("%s delivered: %s", delivered, state)


manager = StateManager("color", "#abcdef")


async def ws_handler(websocket):
    manager.add(websocket)
    try:
        await websocket.send(manager.state)
        async for message in websocket:
            await manager.publish(message)
    finally:
        manager.remove(websocket)


async def main():
    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    loop.add_signal_handler(signal.SIGTERM, stop.set_result, None)

    await manager.setup(getenv("REDIS", "redis://localhost/0"))

    async with websockets.serve(
        ws_handler,
        host=getenv("HOST", "localhost"),
        port=int(getenv("PORT", "5000")),
        logger=logging.getLogger("ws"),
    ):
        await stop

    await manager.teardown()


logging.basicConfig(level=logging.DEBUG if getenv("DEBUG") else logging.INFO)
asyncio.run(main())
