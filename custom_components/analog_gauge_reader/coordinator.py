"""DataUpdateCoordinator for Analog Gauge Reader."""
from __future__ import annotations

from datetime import timedelta
import logging
import urllib.request
import ssl

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    CONF_SNAPSHOT_URL,
    CONF_INTERVAL,
    CONF_MIN_READING,
    CONF_MAX_READING,
)
from .image_processing import process_gauge_image

_LOGGER = logging.getLogger(__name__)


def fetch_image_sync(url: str, timeout: int = 30) -> bytes:
    """Fetch image using urllib (more lenient with headers)."""
    # Create SSL context that doesn't verify
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'HomeAssistant/GaugeReader',
            'Accept': 'image/*,*/*',
        }
    )
    
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
        return response.read()


class GaugeCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the camera and processing it."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.entry = entry
        interval_minutes = entry.data.get(CONF_INTERVAL, 15)
        update_interval = timedelta(minutes=int(interval_minutes))

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self):
        """Fetch data from camera snapshot URL and process it."""
        snapshot_url = self.entry.data[CONF_SNAPSHOT_URL]
        min_reading = self.entry.data[CONF_MIN_READING]
        max_reading = self.entry.data[CONF_MAX_READING]

        _LOGGER.info("Fetching gauge image from: %s", snapshot_url)

        try:
            # Run synchronous fetch in executor (urllib is more lenient with headers)
            image_bytes = await self.hass.async_add_executor_job(
                fetch_image_sync,
                snapshot_url,
                30
            )
            
            if len(image_bytes) < 1000:
                raise UpdateFailed("Image too small, camera may be offline")
                
            _LOGGER.debug("Got image, size: %d bytes", len(image_bytes))

        except Exception as err:
            _LOGGER.error("Error fetching image: %s", err)
            raise UpdateFailed(f"Error fetching image: {err}")

        # Process image
        try:
            value = await self.hass.async_add_executor_job(
                process_gauge_image,
                image_bytes,
                min_reading,
                max_reading
            )
            
            if value is None:
                _LOGGER.warning("Could not detect gauge reading from image")
                return None
                
            _LOGGER.info("Gauge reading: %.2f", value)
            return value
            
        except Exception as proc_err:
            _LOGGER.error("Image processing error: %s", proc_err)
            raise UpdateFailed(f"Processing error: {proc_err}")
