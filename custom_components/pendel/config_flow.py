"""Setup dialog: connect to Pendel, then choose the person and the zones to track."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN, CONF_URL
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PendelAuthError, PendelClient, PendelError, normalize_url
from .const import CONF_HOME_ZONE, CONF_OFFICE_ZONE, CONF_PERSON, CONF_TRACK_LOCATION, DOMAIN

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
        ),
        vol.Required(CONF_EMAIL): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(
                type=selector.TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
    }
)


def tracking_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_TRACK_LOCATION, default=defaults.get(CONF_TRACK_LOCATION, True)): bool,
            vol.Optional(CONF_PERSON, description={"suggested_value": defaults.get(CONF_PERSON)}): (
                selector.EntitySelector(selector.EntitySelectorConfig(domain="person"))
            ),
            vol.Optional(
                CONF_HOME_ZONE, description={"suggested_value": defaults.get(CONF_HOME_ZONE, "zone.home")}
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="zone")),
            vol.Optional(CONF_OFFICE_ZONE, description={"suggested_value": defaults.get(CONF_OFFICE_ZONE)}): (
                selector.EntitySelector(selector.EntitySelectorConfig(domain="zone"))
            ),
        }
    )


def validate_tracking(data: Mapping[str, Any]) -> dict[str, str]:
    if not data.get(CONF_TRACK_LOCATION):
        return {}
    errors = {}
    for key in (CONF_PERSON, CONF_HOME_ZONE, CONF_OFFICE_ZONE):
        if not data.get(key):
            errors[key] = "required_for_tracking"
    if not errors and data[CONF_HOME_ZONE] == data[CONF_OFFICE_ZONE]:
        errors[CONF_OFFICE_ZONE] = "same_zone"
    return errors


async def sync_zones(client: PendelClient, data: Mapping[str, Any]) -> None:
    """Write the chosen zones to the places in Pendel so its rules know home and office."""
    if data.get(CONF_TRACK_LOCATION):
        await client.set_place_zone("home", data[CONF_HOME_ZONE])
        await client.set_place_zone("office", data[CONF_OFFICE_ZONE])


class PendelConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._url = ""
        self._token = ""
        self._name = ""

    async def _login(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Create a token; returns form errors."""
        session = async_get_clientsession(self.hass)
        url = normalize_url(user_input[CONF_URL])
        try:
            token = await PendelClient.create_token(
                session, url, user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            me = await PendelClient(session, url, token).me()
        except PendelAuthError:
            return {"base": "invalid_auth"}
        except PendelError:
            return {"base": "cannot_connect"}
        self._url, self._token, self._name = url, token, me["display_name"]
        await self.async_set_unique_id(f"{url}#{me['id']}")
        return {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._login(user_input)
            if not errors:
                self._abort_if_unique_id_configured()
                return await self.async_step_tracking()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_tracking(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = validate_tracking(user_input)
            if not errors:
                client = PendelClient(async_get_clientsession(self.hass), self._url, self._token)
                try:
                    await sync_zones(client, user_input)
                except PendelError:
                    errors = {"base": "cannot_connect"}
                else:
                    return self.async_create_entry(
                        title=f"Pendel ({self._name})",
                        data={CONF_URL: self._url, CONF_TOKEN: self._token, **user_input},
                    )
        defaults = user_input or {CONF_PERSON: self._default_person()}
        return self.async_show_form(step_id="tracking", data_schema=tracking_schema(defaults), errors=errors)

    def _default_person(self) -> str | None:
        persons = self.hass.states.async_entity_ids("person")
        return persons[0] if len(persons) == 1 else None

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._login({CONF_URL: entry.data[CONF_URL], **user_input})
            if not errors:
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: self._token})
        schema = vol.Schema({vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str})
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
            description_placeholders={"url": entry.data[CONF_URL]},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PendelOptionsFlow()


class PendelOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            errors = validate_tracking(user_input)
            if not errors:
                try:
                    await sync_zones(self.config_entry.runtime_data.client, user_input)
                except PendelError:
                    errors = {"base": "cannot_connect"}
                else:
                    return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init", data_schema=tracking_schema(user_input or current), errors=errors
        )
