"""WWZ API client."""

from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import aiohttp

from .const import (
    API_BASE_URL,
    API_CONTRACT_ACCOUNTS_PATH,
    API_DATA_PATH,
    API_METER_POINT_ID_PATH,
    API_METER_POINTS_PATH,
    API_PORTAL_PATH,
    API_READ_TOKEN_PATH,
    IAM_AUTHORIZE_PATH,
    IAM_PASSWORD_CHECK_PATH,
    IAM_REST_URL,
)

_LOGGER = logging.getLogger(__name__)

_COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

_IAM_HEADERS = {"X-Same-Domain": "1", "Accept": "application/json"}


class WwzApiError(Exception):
    """Base exception for WWZ API errors."""


class WwzAuthError(WwzApiError):
    """Authentication failed."""


class WwzApiClient:
    """Client for the WWZ smart meter API.

    Login runs the energieportal OAuth2 flow against the Airlock IAM REST API
    on cockpit.wwz.ch, then exchanges the authorization code at www.wwz.ch,
    which sets the .ASPXAUTH session cookie used by the /api/stromportal
    endpoints.
    """

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password
        self._session: aiohttp.ClientSession | None = None
        self._contract_account_id: str | None = None
        self._meter_number: str | None = None
        self._meter_id: str | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            jar = aiohttp.CookieJar(unsafe=True)
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(
                headers=_COMMON_HEADERS,
                cookie_jar=jar,
                timeout=timeout,
            )
        return self._session

    async def login(self) -> None:
        """Full authentication flow: OAuth2 login → code exchange → session warmup."""
        session = await self._ensure_session()
        session.cookie_jar.clear()

        # Step 1: Portal redirects to the authorize endpoint (carries PKCE challenge and state)
        try:
            async with session.get(f"{API_BASE_URL}{API_PORTAL_PATH}") as resp:
                authorize = next(
                    (h.url for h in resp.history if "/authorize" in h.url.path),
                    None,
                )
                if authorize is None:
                    raise WwzApiError(
                        f"Portal did not redirect to login (status {resp.status})"
                    )
                query_string = authorize.raw_query_string
        except aiohttp.ClientError as err:
            raise WwzApiError(f"Failed to start login: {err}") from err

        authorize_url = f"{IAM_REST_URL}{IAM_AUTHORIZE_PATH}"
        try:
            # Step 2: Start the IAM flow for this authorization request
            async with session.post(
                authorize_url, json={"queryString": query_string}, headers=_IAM_HEADERS
            ) as resp:
                _LOGGER.debug("Authorize: status=%s", resp.status)
                if resp.status >= 500:
                    raise WwzApiError(f"Login failed with status {resp.status}")

            # Step 3: Username/password step
            async with session.post(
                f"{IAM_REST_URL}{IAM_PASSWORD_CHECK_PATH}",
                json={"username": self._username, "password": self._password},
                headers=_IAM_HEADERS,
            ) as resp:
                if resp.status in (400, 401, 403):
                    body = await resp.json(content_type=None)
                    codes = [e.get("code") for e in body.get("errors") or []]
                    raise WwzAuthError(f"Login failed: {', '.join(map(str, codes))}")
                if resp.status != 200:
                    # Portal outages (e.g. 503) are transient, not bad credentials
                    raise WwzApiError(f"Login failed with status {resp.status}")

            # Step 4: Complete the authorization; X-Forward-URL holds the redirect with the code
            async with session.post(
                authorize_url, json={"queryString": query_string}, headers=_IAM_HEADERS
            ) as resp:
                forward_url = resp.headers.get("X-Forward-URL")
                if resp.status != 200 or not forward_url:
                    raise WwzApiError(
                        f"Authorization failed with status {resp.status}"
                    )
        except aiohttp.ClientError as err:
            raise WwzApiError(f"Connection error during login: {err}") from err

        # Step 5: Exchange the code at www.wwz.ch for the portal session cookie
        params = parse_qs(urlsplit(forward_url).query)
        form = aiohttp.FormData(
            {
                "hash": "",
                "code": params.get("code", [""])[0],
                "state": params.get("state", [""])[0],
                "returnto": "",
            },
            default_to_multipart=True,
        )
        try:
            async with session.post(
                f"{API_BASE_URL}{API_READ_TOKEN_PATH}", data=form
            ) as resp:
                if resp.status != 200:
                    raise WwzApiError(f"Token exchange failed with status {resp.status}")
                _LOGGER.debug("Login successful")
        except aiohttp.ClientError as err:
            raise WwzApiError(f"Connection error during token exchange: {err}") from err

        # Step 6: Warm up session context for smart meter access
        await self._setup_meter_context(session)

    async def _setup_meter_context(self, session: aiohttp.ClientSession) -> None:
        """Call contractAccounts → getMeterPoints → getMeterPointId.

        These calls set up server-side state required for getDiagramValues.
        """
        # contractAccounts → get caId
        try:
            async with session.get(f"{API_BASE_URL}{API_CONTRACT_ACCOUNTS_PATH}") as resp:
                body = await resp.json(content_type=None)
                accounts = body.get("data", [])
                if not accounts:
                    raise WwzApiError("No contract accounts found")
                self._contract_account_id = accounts[0].get("caId")
                _LOGGER.debug("Contract account: %s", self._contract_account_id)
        except (aiohttp.ClientError, ValueError) as err:
            raise WwzApiError(f"Failed to get contract accounts: {err}") from err

        # getMeterPoints → get meterPointNumber
        try:
            async with session.get(
                f"{API_BASE_URL}{API_METER_POINTS_PATH}",
                params={"contractAccount": self._contract_account_id},
            ) as resp:
                body = await resp.json()
                contracts = (body.get("data") or {}).get("contracts", [])
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
                data = body.get("data") or {}
                self._meter_id = str(data.get("meterId", ""))
                if not self._meter_id:
                    raise WwzApiError("API returned no meter ID")
                _LOGGER.debug("Meter ID: %s", self._meter_id)
        except aiohttp.ClientError as err:
            raise WwzApiError(f"Failed to get meter point ID: {err}") from err

    @property
    def meter_id(self) -> str | None:
        """Return the discovered meter ID."""
        return self._meter_id

    async def get_hourly_data(
        self,
        meter_id: str,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> dict:
        """Fetch hourly energy data for a date range.

        Args:
            meter_id: The smart meter ID.
            from_date: Start date (defaults to today).
            to_date: End date (defaults to from_date, i.e. single day).

        Returns dict with "values" and "unit".
        """
        cet = ZoneInfo("Europe/Zurich")
        if from_date is None:
            from_date = datetime.now(tz=cet)
        if to_date is None:
            to_date = from_date

        from_midnight = from_date.astimezone(cet).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        to_midnight = to_date.astimezone(cet).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        from_ms = int(from_midnight.timestamp() * 1000)
        to_ms = int(to_midnight.timestamp() * 1000)

        url = f"{API_BASE_URL}{API_DATA_PATH}"
        params = {
            "type": "consumption",
            "from": str(from_ms),
            "id": meter_id,
            "interval": "HOUR",
            "until": str(to_ms),
        }

        data = await self._get_json_with_reauth(url, params)
        inner = data["data"]
        return {
            "values": inner.get("values", []),
            "unit": inner.get("unit", "kWh"),
        }

    async def _get_json_with_reauth(self, url: str, params: dict) -> dict:
        """GET a JSON endpoint, re-authenticating and retrying once on any failure."""
        last_err: Exception | None = None
        for attempt in (1, 2):
            if attempt == 2:
                _LOGGER.debug("Retrying after failure, re-authenticating: %s", last_err)
                await self.login()

            session = await self._ensure_session()
            try:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        body_preview = (await resp.text())[:200]
                        last_err = WwzApiError(
                            f"API request failed ({resp.status}): {body_preview}"
                        )
                        continue
                    data = await resp.json(content_type=None)
            except (aiohttp.ClientError, ValueError) as err:
                last_err = WwzApiError(f"Request error: {err}")
                continue

            if data and data.get("data") is not None:
                return data

            msg_text = (
                data.get("frontEndMessage", {}).get("message", "unknown")
                if data
                else "empty response"
            )
            last_err = WwzApiError(f"API returned no data: {msg_text}")

        assert last_err is not None
        raise last_err

    async def close(self) -> None:
        """Close the API session."""
        if self._session and not self._session.closed:
            await self._session.close()
