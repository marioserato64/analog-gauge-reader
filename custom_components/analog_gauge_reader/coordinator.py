"""DataUpdateCoordinator for Analog Gauge Reader."""
from __future__ import annotations

from datetime import timedelta
import logging
import io

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.components.camera import async_get_image

from .const import (
    DOMAIN,
    CONF_CAMERA_ENTITY,
    CONF_INTERVAL,
    CONF_MIN_READING,
    CONF_MAX_READING,
)
from .image_processing import process_gauge_image

_LOGGER = logging.getLogger(__name__)

class GaugeCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the camera and processing it."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.entry = entry
        interval_str = entry.data.get(CONF_INTERVAL, "15 minutes")
        if interval_str == "1 minute":
            update_interval = timedelta(minutes=1)
        else:
            update_interval = timedelta(minutes=15)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self):
        """Fetch data from camera and process it."""
        camera_entity = self.entry.data[CONF_CAMERA_ENTITY]
        min_reading = self.entry.data[CONF_MIN_READING]
        max_reading = self.entry.data[CONF_MAX_READING]

        try:
            # Get image from camera
            image_data = await async_get_image(self.hass, camera_entity)
            
            # Process image in executor to avoid blocking loop
            # image_data.content is bytes
            value = await self.hass.async_add_executor_job(
                process_gauge_image,
                image_data.content,
                min_reading,
                max_reading
            )
            
            return value
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
