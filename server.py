import asyncio
import logging
import signal
from os import getenv

import websockets

color = "#abcdef"

connected = set()


async def ws_handler(websocket):
    global color, connected
    connected.add(websocket)
    try:
        await websocket.send(color)
        async for message in websocket:
            color = message
            websockets.broadcast(connected, color)
    finally:
        connected.remove(websocket)


async def main():
    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    loop.add_signal_handler(signal.SIGTERM, stop.set_result, None)

    host = getenv("HOST", "localhost")
    port = int(getenv("PORT", "5000"))
    logger = logging.getLogger("ws")
    async with websockets.serve(ws_handler, host=host, port=port, logger=logger):
        await stop


logging.basicConfig(level=logging.DEBUG)
asyncio.run(main())
