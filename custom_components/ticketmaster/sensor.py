"""Sensors for the Ticketmaster integration."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.components.sensor import (
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TicketmasterCoordinator

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="next_event",
        name="Next event",
        icon="mdi:calendar-star",
        translation_key="next_event",
    ),
    SensorEntityDescription(
        key="next_event_starts_at",
        name="Next event starts at",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_event_starts_at",
    ),
    SensorEntityDescription(
        key="next_event_venue",
        name="Next event venue",
        icon="mdi:map-marker",
        translation_key="next_event_venue",
    ),
    SensorEntityDescription(
        key="next_event_url",
        name="Next event URL",
        icon="mdi:ticket-confirmation",
        translation_key="next_event_url",
    ),
    SensorEntityDescription(
        key="upcoming_events",
        name="Upcoming events",
        icon="mdi:calendar-month",
        translation_key="upcoming_events",
        native_unit_of_measurement="events",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


class TicketmasterSensor(CoordinatorEntity[TicketmasterCoordinator], SensorEntity):
    """Representation of a Ticketmaster sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TicketmasterCoordinator,
        description: SensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def _next_event(self) -> dict[str, Any] | None:
        """Return the next upcoming event, if any."""
        events = self.coordinator.data or []
        if not events:
            return None
        now = datetime.now()
        for event in events:
            start: datetime = event["start"]
            if start.replace(tzinfo=None) >= now.replace(tzinfo=None):
                return event
        return None

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        event = self._next_event
        if event is None:
            return None
        key = self.entity_description.key
        if key == "next_event":
            return self._format_name(event)
        if key == "next_event_starts_at":
            return event["start"]
        if key == "next_event_venue":
            return self._format_venue(event)
        if key == "next_event_url":
            return event.get("url")
        if key == "upcoming_events":
            return len(self.coordinator.data or [])
        return None

    def _format_name(self, event: dict[str, Any]) -> str:
        name = event.get("name") or "Unknown event"
        lineup = event.get("lineup") or []
        if lineup and lineup[0] and lineup[0] not in name:
            return f"{lineup[0]}: {name}"
        return name

    def _format_venue(self, event: dict[str, Any]) -> str:
        venue = event.get("venue") or {}
        if not venue:
            return "Unknown venue"
        name = venue.get("name") or "Unknown venue"
        city = (venue.get("city") or {}).get("name") or ""
        return f"{name}, {city}".rstrip(", ") if city else name

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return event provider and ticket link as attributes."""
        key = self.entity_description.key
        if key == "upcoming_events":
            now = datetime.now()
            events = self.coordinator.data or []
            upcoming = [
                {
                    "name": event.get("name"),
                    "start": event["start"].isoformat(),
                    "venue": (event.get("venue") or {}).get("name"),
                    "source": event.get("source"),
                    "url": event.get("url"),
                }
                for event in events
                if event["start"].replace(tzinfo=None) >= now.replace(tzinfo=None)
            ]
            return {"events": upcoming}
        event = self._next_event
        if event is None:
            return None
        if key == "next_event":
            return {"source": event.get("source"), "url": event.get("url")}
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ticketmaster sensors from a config entry."""
    coordinator: TicketmasterCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        TicketmasterSensor(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS
    )