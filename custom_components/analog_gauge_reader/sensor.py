"""Sensor platform for Analog Gauge Reader."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPressure
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GaugeCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    # We should have stored the coordinator in hass.data in __init__, but we didn't. 
    # Let's create it here or fix __init__.
    # Actually, standard pattern is to create coordinator in __init__.
    # Let's fix __init__ later if needed, but for now let's create it here? 
    # No, ConfigEntry setup should be in __init__.
    
    # Wait, I didn't instantiate coordinator in __init_py.
    # I should have done:
    # coordinator = GaugeCoordinator(hass, entry)
    # await coordinator.async_config_entry_first_refresh()
    # hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # I will assume I will fix __init__.py in next step.
    
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([GaugeSensor(coordinator, entry)])

class GaugeSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Gauge Sensor."""

    _attr_has_entity_name = True
    _attr_name = "Pressure"
    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_native_unit_of_measurement = UnitOfPressure.BAR
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: GaugeCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_pressure"
        # self._attr_name = "Gauge Pressure" # Entity name

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.coordinator.data
