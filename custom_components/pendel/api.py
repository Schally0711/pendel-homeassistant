"""Small async client for the Pendel REST API."""

from __future__ import annotations

from typing import Any

import aiohttp

from .const import TOKEN_NAME


class PendelError(Exception):
    """Base error."""


class PendelConnectionError(PendelError):
    """Pendel is not reachable or answered with a server error."""


class PendelAuthError(PendelError):
    """Token or credentials were rejected."""


class PendelTotpRequired(PendelAuthError):
    """The account uses two-factor authentication: a code is needed (or the given one was wrong)."""

    def __init__(self, invalid: bool = False) -> None:
        super().__init__("invalid_totp" if invalid else "totp_required")
        self.invalid = invalid


class PendelConflictError(PendelError):
    """The action does not fit the current state (e.g. no session running)."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def normalize_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.removesuffix("/api")


class PendelClient:
    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        self._session = session
        self.url = normalize_url(url)
        self._token = token

    async def _request(self, method: str, path: str, json: Any = None) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self.url}/api{path}",
                json=json,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status == 401:
                    raise PendelAuthError
                if resp.status in (404, 409, 422):
                    detail = (await resp.json(content_type=None) or {}).get("detail", str(resp.status))
                    raise PendelConflictError(detail if isinstance(detail, str) else "invalid_request")
                if resp.status >= 400:
                    raise PendelConnectionError(f"HTTP {resp.status}")
                if resp.status == 204:
                    return None
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise PendelConnectionError(str(err)) from err

    @staticmethod
    async def create_token(
        session: aiohttp.ClientSession, url: str, email: str, password: str, totp: str | None = None
    ) -> str:
        """Exchange e-mail + password (+ 2FA code) for an API token."""
        body = {"email": email, "password": password, "name": TOKEN_NAME}
        if totp:
            body["totp"] = totp
        try:
            async with session.post(
                f"{normalize_url(url)}/api/auth/token", json=body, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                if resp.status == 401:
                    detail = (await resp.json(content_type=None)).get("detail")
                    if detail in ("totp_required", "invalid_totp"):
                        raise PendelTotpRequired(invalid=detail == "invalid_totp")
                    raise PendelAuthError
                if resp.status == 429:
                    raise PendelAuthError
                if resp.status != 201:
                    raise PendelConnectionError(f"HTTP {resp.status}")
                return (await resp.json(content_type=None))["token"]
        except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as err:
            raise PendelConnectionError(str(err)) from err

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/health")

    async def me(self) -> dict[str, Any]:
        return await self._request("GET", "/me")

    async def today(self) -> dict[str, Any]:
        return await self._request("GET", "/today")

    async def vacation(self, year: int) -> dict[str, Any]:
        return await self._request("GET", f"/vacation/{year}")

    async def absences(self, year: int) -> dict[str, Any]:
        return await self._request("GET", f"/absences?year={year}")

    async def places(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/places")

    async def set_place_zone(self, kind: str, zone: str) -> None:
        """Set the zone of the first active place of a kind (home/office)."""
        for place in await self.places():
            if place["kind"] == kind and not place["archived"]:
                body = {k: v for k, v in place.items() if k != "id"} | {"zone": zone}
                await self._request("PUT", f"/places/{place['id']}", body)
                return

    async def send_zone_change(self, old: str, new: str, at: str) -> list[dict[str, Any]]:
        result = await self._request(
            "POST",
            "/events",
            {"type": "zone_change", "from": old, "to": new, "at": at, "source": "home_assistant"},
        )
        return result["events"]

    async def clock(self, action: str, body: dict[str, Any] | None = None) -> None:
        await self._request("POST", f"/clock/{action}", body or {})
