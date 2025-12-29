"""Config flow for Analog Gauge Reader integration."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .const import (
    DOMAIN,
    CONF_SNAPSHOT_URL,
    CONF_INTERVAL,
    CONF_MIN_READING,
    CONF_MAX_READING,
    CONF_ALARM_1,
    CONF_ALARM_2,
    CONF_ALARM_3,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Analog Gauge Reader."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # Validate URL
            url = user_input.get(CONF_SNAPSHOT_URL, "")
            if not url.startswith("http"):
                errors[CONF_SNAPSHOT_URL] = "invalid_url"
            else:
                return self.async_create_entry(
                    title=f"Gauge Reader",
                    data=user_input
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_SNAPSHOT_URL): str,
                vol.Required(CONF_INTERVAL, default=15): vol.All(
                    vol.Coerce(int), vol.In([1, 15])
                ),
                vol.Required(CONF_MIN_READING, default=0.0): vol.Coerce(float),
                vol.Required(CONF_MAX_READING, default=3.0): vol.Coerce(float),
                vol.Optional(CONF_ALARM_1): vol.Coerce(float),
                vol.Optional(CONF_ALARM_2): vol.Coerce(float),
                vol.Optional(CONF_ALARM_3): vol.Coerce(float),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )
