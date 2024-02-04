import asyncio
import typing


class AsyncJolt:
    async def __aenter__(self) -> None:
        await asyncio.sleep(0)

    async def __aexit__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        await asyncio.sleep(0)
