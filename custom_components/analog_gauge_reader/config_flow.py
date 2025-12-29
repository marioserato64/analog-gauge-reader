"""Config flow for Analog Gauge Reader integration."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_CAMERA_ENTITY,
    CONF_INTERVAL,
    CONF_MIN_READING,
    CONF_MAX_READING,
    CONF_ALARM_1,
    CONF_ALARM_2,
    CONF_ALARM_3,
    DEFAULT_INTERVAL,
    interval_options
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Analog Gauge Reader."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title=f"Gauge Reader ({user_input[CONF_CAMERA_ENTITY]})",
                data=user_input
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_CAMERA_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="camera")
                ),
                vol.Required(CONF_INTERVAL, default=DEFAULT_INTERVAL): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=interval_options,
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
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
