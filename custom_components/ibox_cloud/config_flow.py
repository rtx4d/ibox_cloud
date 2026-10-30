"""Config flow for iBOX Cloud: phone number -> SMS/call code -> token."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IboxApiClient, IboxAuthError, IboxError
from .const import (
    AUTH_SMS,
    AUTH_WAIT_CALL,
    CALL_CODE,
    CONF_AUTH_TYPE,
    CONF_PHONE,
    CONF_SHOW_PANEL,
    CONF_TOKEN,
    DOMAIN,
)


class IboxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the iBOX Cloud config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return IboxOptionsFlow()

    def __init__(self) -> None:
        self._phone: str | None = None
        self._use_call: bool = False
        self._call_number: str | None = None
        self._client: IboxApiClient | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._phone = "".join(ch for ch in user_input[CONF_PHONE] if ch.isdigit())
            self._use_call = user_input.get("use_call", False)
            token = (user_input.get(CONF_TOKEN) or "").strip()
            self._client = IboxApiClient(async_get_clientsession(self.hass), token=token or None)
            await self.async_set_unique_id(self._phone)
            self._abort_if_unique_id_configured()
            if token:
                # Reuse a token obtained earlier: avoids another login (the server rate-limits them)
                try:
                    valid = await self._client.check_token()
                except IboxError:
                    errors["base"] = "cannot_connect"
                else:
                    if valid:
                        return self.async_create_entry(
                            title=self._phone,
                            data={CONF_PHONE: self._phone, CONF_TOKEN: token, CONF_AUTH_TYPE: None},
                        )
                    errors["base"] = "invalid_token"
                return self._show_user_form(errors)
            try:
                resp = await self._client.request_code(self._phone, is_sms=not self._use_call)
            except IboxError:
                errors["base"] = "cannot_connect"
            else:
                # The server may switch an SMS request to a call: type 3 and the number to call.
                if isinstance(resp, dict) and resp.get("type") == AUTH_WAIT_CALL:
                    self._use_call = True
                    self._call_number = resp.get("replaced_from")
                if self._use_call:
                    return await self.async_step_call()
                return await self.async_step_code()
        return self._show_user_form(errors)

    def _show_user_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        schema = vol.Schema(
            {
                vol.Required(CONF_PHONE): str,
                vol.Optional("use_call", default=False): bool,
                vol.Optional(CONF_TOKEN): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            result = await self._verify(user_input["code"].strip(), AUTH_SMS, errors)
            if result:
                return result
        schema = vol.Schema({vol.Required("code"): str})
        return self.async_show_form(step_id="code", data_schema=schema, errors=errors)

    async def async_step_call(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            result = await self._verify(CALL_CODE, AUTH_WAIT_CALL, errors)
            if result:
                return result
        number = self._call_number
        return self.async_show_form(
            step_id="call",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={"number": f"+{number}" if number else "—"},
        )

    async def _verify(
        self, code: str, auth_type: int, errors: dict[str, str]
    ) -> ConfigFlowResult | None:
        assert self._client and self._phone
        try:
            token = await self._client.verify_code(self._phone, code, auth_type)
        except IboxAuthError:
            errors["base"] = "invalid_code"
        except IboxError:
            errors["base"] = "cannot_connect"
        else:
            return self.async_create_entry(
                title=self._phone,
                data={
                    CONF_PHONE: self._phone,
                    CONF_TOKEN: token,
                    CONF_AUTH_TYPE: auth_type,
                },
            )
        return None


class IboxOptionsFlow(OptionsFlow):
    """Integration options: whether the "iBOX" sidebar panel is shown."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            # keep internal flags stored in the options alongside the user's choices
            return self.async_create_entry(data={**self.config_entry.options, **user_input})
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SHOW_PANEL, default=self.config_entry.options.get(CONF_SHOW_PANEL, True)
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
