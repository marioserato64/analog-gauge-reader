"""Binary Sensor platform for Analog Gauge Reader Alarms."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_ALARM_1,
    CONF_ALARM_2,
    CONF_ALARM_3,
)
from .coordinator import GaugeCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    sensors = []
    
    if entry.data.get(CONF_ALARM_1):
        sensors.append(GaugeAlarmSensor(coordinator, entry, 1, entry.data[CONF_ALARM_1]))
    if entry.data.get(CONF_ALARM_2):
        sensors.append(GaugeAlarmSensor(coordinator, entry, 2, entry.data[CONF_ALARM_2]))
    if entry.data.get(CONF_ALARM_3):
        sensors.append(GaugeAlarmSensor(coordinator, entry, 3, entry.data[CONF_ALARM_3]))
        
    async_add_entities(sensors)

class GaugeAlarmSensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Gauge Alarm Sensor."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: GaugeCoordinator, entry: ConfigEntry, level: int, threshold: float) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_alarm_{level}"
        self._attr_name = f"Pressure Alarm {level}"
        self.threshold = threshold
        self.level = level

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.coordinator.data is None:
            return None
            
        # Alarm triggers if pressure is above threshold? Or below?
        # Usually boiler alarms are for high pressure (safety valve).
        # But low pressure is also bad.
        # Impl: Simplest is > threshold. 
        # But if the user sets 0.5 (low) and 2.5 (high), we need logic.
        # User said "Warning logic".
        # Let's assume > Threshold for now as typical for "Safety Valve 3 bar".
        # Unless threshold is very low (< 1.0), then maybe < Threshold?
        # Heuristic: if threshold > 1.5 (midpoint), assume High Alarm. If < 1.5, Low Alarm?
        # Let's stick to "Alarm if Value >= Threshold" for simplicity unless user specified.
        # Wait, usually multiple thresholds imply stages: Warning 1, Warning 2, Critical.
        # So Value >= Threshold makes sense.
        
        return self.coordinator.data >= self.threshold
