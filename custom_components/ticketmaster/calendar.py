"""Calendar platform for the Ticketmaster integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import TicketmasterCoordinator

SOURCE_TAGS = {
    "ticketmaster": "TM",
    "fatsoma": "FS",
    "skiddle": "SK",
}


class TicketmasterCalendar(CalendarEntity):
    """Representation of a Ticketmaster events calendar."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar-star"

    def __init__(
        self,
        coordinator: TicketmasterCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the calendar."""
        self._coordinator = coordinator
        self._attr_name = "Events"
        self._attr_unique_id = f"{entry.entry_id}_calendar"

    @property
    def available(self) -> bool:
        """Return True if the coordinator data is available."""
        return self._coordinator.last_update_success

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next event."""
        events = self._coordinator.data or []
        if not events:
            return None
        now = dt_util.now()
        for event in events:
            if event["start"] >= now:
                return self._to_calendar_event(event)
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return events within the given time range."""
        events = self._coordinator.data or []
        return [
            self._to_calendar_event(event)
            for event in events
            if start_date <= event["start"] <= end_date
        ]

    def _to_calendar_event(self, event: dict[str, Any]) -> CalendarEvent:
        """Convert a raw API event into a CalendarEvent."""
        start: datetime = event["start"]
        end = start + timedelta(hours=3)
        venue = event.get("venue") or {}
        name = event.get("name") or "Unknown event"
        location = None
        if venue:
            name_str = venue.get("name")
            city = (venue.get("city") or {}).get("name")
            location = " / ".join(x for x in [name_str, city] if x)
        source = event.get("source")
        tag = SOURCE_TAGS.get(source or "")
        summary = f"[{tag}] {name}" if tag else name
        parts = list(event.get("lineup") or [])
        if event.get("url"):
            parts.append(event["url"])
        return CalendarEvent(
            summary=summary,
            start=start,
            end=end,
            location=location,
            description=" / ".join(parts),
            uid=str(event.get("id") or ""),
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ticketmaster calendar from a config entry."""
    coordinator: TicketmasterCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TicketmasterCalendar(coordinator, entry)])