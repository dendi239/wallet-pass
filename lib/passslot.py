import io
import os
import typing as tp
from dataclasses import dataclass

import aiohttp

from lib.ticket import Ticket

PASSSLOT_API_KEY = os.environ["PASSSLOT_API_KEY"]


Response = tp.Dict[str, str]


class CreationPassError(Exception):
    pass


@dataclass
class Pass:
    name: str
    pkpass: tp.BinaryIO


async def register_pass(data: Ticket) -> Response:
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.passslot.com/v1/templates/5786360806637568/pass",
            headers={"Authorization": PASSSLOT_API_KEY},
            json=data,
        ) as response:
            assert response.status == 201, response
            return await response.json()


def _make_pkpass(url: str) -> str:
    i = url.find("?")
    return url[:i] + ".pkpass" + url[i:]


async def validate_pass(response: Response) -> Pass:
    for key in ("url", "serialNumber"):
        if key not in response:
            raise CreationPassError(f"No '{key}' in response: {response}")

    id_ = response["serialNumber"]
    async with aiohttp.ClientSession() as session:
        url = _make_pkpass(response["url"])
        async with session.get(url) as resp:
            resp.raise_for_status()
            pkpass = io.BytesIO(await resp.read())

    return Pass(name=id_, pkpass=pkpass)


async def create_pass(ticket: Ticket) -> Pass:
    response = await register_pass(ticket)
    return await validate_pass(response)
