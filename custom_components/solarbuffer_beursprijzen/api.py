"""Ophalen van de openbare prijzen van SolarBuffer."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import API_URL


class PrijzenFout(Exception):
    """De prijzen konden niet worden opgehaald."""


async def haal_prijzen(sessie: aiohttp.ClientSession) -> dict[str, Any]:
    """Het hele antwoord: beursprijs per uur en de prijs per leverancier."""
    try:
        async with asyncio.timeout(20):
            async with sessie.get(API_URL, headers={"Accept": "application/json"}) as antw:
                if antw.status != 200:
                    raise PrijzenFout(f"server gaf {antw.status}")
                data = await antw.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError) as err:
        raise PrijzenFout(str(err)) from err
    if not isinstance(data, dict) or not isinstance(data.get("uren"), list):
        raise PrijzenFout("onverwacht antwoord van de server")
    return data
