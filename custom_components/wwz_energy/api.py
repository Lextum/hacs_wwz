"""WWZ API client."""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp

from .const import (
    API_BASE_URL,
    API_CONTRACT_ACCOUNTS_PATH,
    API_DATA_PATH,
    API_LOGIN_PATH,
    API_METER_POINT_ID_PATH,
    API_METER_POINTS_PATH,
    API_VALIDATION_PATH,
)

_LOGGER = logging.getLogger(__name__)

_COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://portal.wwz.ch",
    "Referer": "https://portal.wwz.ch/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}


class WwzApiError(Exception):
    """Base exception for WWZ API errors."""


class WwzAuthError(WwzApiError):
    """Authentication failed."""


class WwzApiClient:
    """Client for the WWZ smart meter API.

    The WWZ portal uses cookie-based sessions (AL_SESS-S). After login the
    server must be "warmed up" by calling contractAccounts, getMeterPoints, and
    getMeterPointId — these set up server-side context that authorises the
    getDiagramValues endpoint.
    """

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password
        self._session: aiohttp.ClientSession | None = None
        self._token: dict | None = None
        self._contract_account_id: str | None = None
        self._meter_number: str | None = None
        self._meter_id: str | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            jar = aiohttp.CookieJar(unsafe=True)
            self._session = aiohttp.ClientSession(
                headers=_COMMON_HEADERS,
                cookie_jar=jar,
            )
        return self._session

    async def login(self) -> None:
        """Full authentication flow: login → validation → session warmup."""
        session = await self._ensure_session()

        # Step 1: Get initial AL_SESS-S cookie
        try:
            async with session.get(API_BASE_URL, allow_redirects=False) as resp:
                _LOGGER.debug("Init: status=%s", resp.status)
        except aiohttp.ClientError as err:
            raise WwzApiError(f"Failed to obtain session: {err}") from err

        # Step 2: Login
        try:
            async with session.post(
                f"{API_BASE_URL}{API_LOGIN_PATH}",
                json={
                    "username": self._username,
                    "password": self._password,
                    "client": "wwz",
                },
            ) as resp:
                if resp.status != 200:
                    raise WwzAuthError(f"Login failed with status {resp.status}")

                body = await resp.json()
                msg = body.get("frontEndMessage", {})
                if msg.get("messageType") != 0:
                    raise WwzAuthError(
                        f"Login failed: {msg.get('message', 'unknown error')}"
                    )

                self._token = body.get("data")
                _LOGGER.debug("Login successful")
        except aiohttp.ClientError as err:
            raise WwzApiError(f"Connection error during login: {err}") from err

        # Step 3: Validation (confirms session is authenticated)
        try:
            async with session.post(
                f"{API_BASE_URL}{API_VALIDATION_PATH}",
                json={"client": "wwz"},
            ) as resp:
                _LOGGER.debug("Validation: status=%s", resp.status)
        except aiohttp.ClientError as err:
            raise WwzApiError(f"Validation failed: {err}") from err

        # Step 4: Warm up session context for smart meter access
        await self._setup_meter_context(session)

    async def _setup_meter_context(self, session: aiohttp.ClientSession) -> None:
        """Call contractAccounts → getMeterPoints → getMeterPointId.

        These calls set up server-side state required for getDiagramValues.
        """
        # contractAccounts → get caId
        try:
            async with session.post(
                f"{API_BASE_URL}{API_CONTRACT_ACCOUNTS_PATH}",
                json={"token": self._token, "client": "wwz"},
            ) as resp:
                body = await resp.json()
                accounts = body.get("data", [])
                if not accounts:
                    raise WwzApiError("No contract accounts found")
                self._contract_account_id = accounts[0].get("caId")
                _LOGGER.debug("Contract account: %s", self._contract_account_id)
        except aiohttp.ClientError as err:
            raise WwzApiError(f"Failed to get contract accounts: {err}") from err

        # getMeterPoints → get meterPointNumber
        try:
            async with session.get(
                f"{API_BASE_URL}{API_METER_POINTS_PATH}",
                params={"contractAccount": self._contract_account_id},
            ) as resp:
                body = await resp.json()
                contracts = body.get("data", {}).get("contracts", [])
                if not contracts:
                    raise WwzApiError("No meter points found")
                self._meter_number = contracts[0].get("meterPointNumber")
                _LOGGER.debug("Meter number: %s", self._meter_number)
        except aiohttp.ClientError as err:
            raise WwzApiError(f"Failed to get meter points: {err}") from err

        # getMeterPointId → get numeric meter ID
        try:
            async with session.get(
                f"{API_BASE_URL}{API_METER_POINT_ID_PATH}",
                params={"meterNumber": self._meter_number},
            ) as resp:
                body = await resp.json()
                self._meter_id = str(body.get("data", {}).get("meterId", ""))
                _LOGGER.debug("Meter ID: %s", self._meter_id)
        except aiohttp.ClientError as err:
            raise WwzApiError(f"Failed to get meter point ID: {err}") from err

    @property
    def meter_id(self) -> str | None:
        """Return the discovered meter ID."""
        return self._meter_id

    async def get_daily_data(
        self, meter_id: str, date: datetime | None = None
    ) -> dict:
        """Fetch hourly energy data for a given day.

        Returns dict with "values", "daily_total", and "unit".
        """
        cet = ZoneInfo("Europe/Zurich")
        if date is None:
            date = datetime.now(tz=cet)

        start_of_day = date.astimezone(cet).replace(hour=0, minute=0, second=0, microsecond=0)
        epoch_ms = int(start_of_day.timestamp() * 1000)

        session = await self._ensure_session()
        url = f"{API_BASE_URL}{API_DATA_PATH}"
        params = {
            "from": str(epoch_ms),
            "id": meter_id,
            "interval": "HOUR",
            "until": str(epoch_ms),
        }

        try:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise WwzApiError(
                        f"API request failed ({resp.status}): {body[:200]}"
                    )
                data = await resp.json()
        except aiohttp.ClientError as err:
            raise WwzApiError(f"Connection error: {err}") from err

        inner = data.get("data") if data else None

        # Re-authenticate on session expiry
        if inner is None:
            msg_text = (
                data.get("frontEndMessage", {}).get("message", "")
                if data
                else ""
            )
            if "not logged in" in msg_text.lower() or "unauthorized" in msg_text.lower():
                _LOGGER.debug("Session expired, re-authenticating")
                await self.login()
                session = await self._ensure_session()
                try:
                    async with session.get(url, params=params) as resp:
                        if resp.status != 200:
                            body = await resp.text()
                            raise WwzApiError(
                                f"API request failed after re-auth ({resp.status}): {body[:200]}"
                            )
                        data = await resp.json()
                except aiohttp.ClientError as err:
                    raise WwzApiError(f"Connection error: {err}") from err
                inner = data.get("data") if data else None

        if inner is None:
            msg_text = (
                data.get("frontEndMessage", {}).get("message", "unknown")
                if data
                else "empty response"
            )
            raise WwzApiError(f"API returned no data: {msg_text}")

        values = inner.get("values", [])
        daily_total = sum(v.get("value", 0) for v in values)

        return {
            "values": values,
            "daily_total": round(daily_total, 3),
            "unit": inner.get("unit", "kWh"),
        }

    async def close(self) -> None:
        """Close the API session."""
        if self._session and not self._session.closed:
            await self._session.close()
