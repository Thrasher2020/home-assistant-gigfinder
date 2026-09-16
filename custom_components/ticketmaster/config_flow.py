"""Config flow for the Ticketmaster integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_FATSOMA_PAGE_IDS,
    CONF_FATSOMA_SEARCH,
    CONF_GENRE,
    CONF_GENRE_ID,
    CONF_RADIUS_MILES,
    CONF_SCAN_INTERVAL,
    CONF_SKIDDLE_API_KEY,
    CONF_SKIDDLE_GENRES,
    CONF_SKIDDLE_SEARCH,
    CONF_SKIDDLE_VENUE_IDS,
    DEFAULT_FATSOMA_PAGE_IDS,
    DEFAULT_GENRE,
    DEFAULT_RADIUS_MILES,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_SKIDDLE_GENRES,
    DEFAULT_SKIDDLE_VENUE_IDS,
    DOMAIN,
    NAME,
    UNITS,
)
from .coordinator import ApiError, TicketmasterApiClient

_LOGGER = logging.getLogger(__name__)

API_KEY_SELECTOR = TextSelector(
    TextSelectorConfig(
        type=TextSelectorType.PASSWORD,
        autocomplete="current-password",
    )
)


def _ensure_options(entry: ConfigEntry) -> dict[str, Any]:
    """Return the stored options with any new defaults filled in."""
    options = dict(entry.options)
    options.setdefault(CONF_RADIUS_MILES, DEFAULT_RADIUS_MILES)
    options.setdefault(CONF_GENRE, DEFAULT_GENRE)
    options.setdefault(CONF_GENRE_ID, "")
    options.setdefault(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES)
    options.setdefault(CONF_FATSOMA_PAGE_IDS, list(DEFAULT_FATSOMA_PAGE_IDS))
    options.setdefault(CONF_SKIDDLE_API_KEY, "")
    options.setdefault(CONF_SKIDDLE_VENUE_IDS, list(DEFAULT_SKIDDLE_VENUE_IDS))
    options.setdefault(CONF_SKIDDLE_GENRES, list(DEFAULT_SKIDDLE_GENRES))
    return options


class TicketmasterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ticketmaster."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = str(user_input[CONF_API_KEY]).strip()
            client = TicketmasterApiClient(self.hass, api_key)
            try:
                await client.async_validate()
            except ApiError as err:
                _LOGGER.error("Ticketmaster API validation failed: %s", err)
                errors["base"] = err.reason
            if not errors:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=NAME,
                    data={CONF_API_KEY: api_key},
                    options={
                        CONF_RADIUS_MILES: DEFAULT_RADIUS_MILES,
                        CONF_GENRE: DEFAULT_GENRE,
                        CONF_GENRE_ID: "",
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_MINUTES,
                        CONF_FATSOMA_PAGE_IDS: list(DEFAULT_FATSOMA_PAGE_IDS),
                        CONF_SKIDDLE_API_KEY: "",
                        CONF_SKIDDLE_VENUE_IDS: list(DEFAULT_SKIDDLE_VENUE_IDS),
                        CONF_SKIDDLE_GENRES: list(DEFAULT_SKIDDLE_GENRES),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): API_KEY_SELECTOR}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> TicketmasterOptionsFlow:
        """Get the options flow for this handler."""
        return TicketmasterOptionsFlow(config_entry)


class TicketmasterOptionsFlow(OptionsFlow):
    """Handle Ticketmaster options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._pending: dict[str, Any] | None = None
        self._search_query = ""

    def _make_client(self) -> TicketmasterApiClient:
        """Build an API client from the stored key."""
        return TicketmasterApiClient(
            self.hass, self._config_entry.data[CONF_API_KEY]
        )

    async def _fetch_genres(self, client: TicketmasterApiClient) -> list[dict[str, str]]:
        """Return the genre list, best-effort."""
        try:
            return await client.async_get_genres()
        except ApiError as err:
            _LOGGER.warning("Could not fetch genre list: %s", err)
            return []

    async def _fetch_skiddle_genres(
        self, client: TicketmasterApiClient, api_key: str
    ) -> list[dict[str, str]]:
        """Return the Skiddle genre list, best-effort."""
        if not api_key:
            return []
        try:
            return await client.async_get_skiddle_genres(api_key)
        except ApiError as err:
            _LOGGER.warning("Could not fetch Skiddle genre list: %s", err)
            return []

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Manage the options."""
        current = _ensure_options(self._config_entry)
        client = self._make_client()
        genres = await self._fetch_genres(client)
        errors: dict[str, str] = {}

        if user_input is not None:
            chosen = str(user_input.get(CONF_GENRE) or "")
            genre_id = next(
                (g["id"] for g in genres if g["name"] == chosen), ""
            )
            skiddle_key = str(user_input.get(CONF_SKIDDLE_API_KEY) or "").strip()
            current_key = str(current.get(CONF_SKIDDLE_API_KEY) or "").strip()
            self._pending = {
                CONF_RADIUS_MILES: user_input[CONF_RADIUS_MILES],
                CONF_GENRE: chosen,
                CONF_GENRE_ID: genre_id,
                CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                CONF_FATSOMA_PAGE_IDS: list(
                    user_input.get(CONF_FATSOMA_PAGE_IDS) or []
                ),
                CONF_SKIDDLE_API_KEY: skiddle_key,
                CONF_SKIDDLE_VENUE_IDS: list(
                    user_input.get(CONF_SKIDDLE_VENUE_IDS) or []
                ),
                CONF_SKIDDLE_GENRES: list(
                    user_input.get(CONF_SKIDDLE_GENRES) or []
                ),
            }
            if skiddle_key and skiddle_key != current_key:
                try:
                    await client.async_validate_skiddle_key(skiddle_key)
                except ApiError as err:
                    errors["base"] = err.reason

            fatsoma_search = str(user_input.get(CONF_FATSOMA_SEARCH) or "").strip()
            skiddle_search = str(user_input.get(CONF_SKIDDLE_SEARCH) or "").strip()
            if not errors:
                if fatsoma_search:
                    self._search_query = fatsoma_search
                    return await self.async_step_fatsoma_pages()
                if skiddle_search:
                    self._search_query = skiddle_search
                    return await self.async_step_skiddle_venues()
                return self.async_create_entry(title="", data=self._pending)

        source = user_input if user_input is not None else (self._pending or current)

        genre_options = [{"label": "All genres", "value": ""}]
        genre_options += [
            {"label": g["name"], "value": g["name"]} for g in genres
        ]
        genre_default = str(source.get(CONF_GENRE) or "")
        if genre_default not in {g["name"] for g in genres}:
            genre_default = ""

        page_options = []
        for page_id in source.get(CONF_FATSOMA_PAGE_IDS) or []:
            page = await client.async_get_fatsoma_page(str(page_id))
            page_options.append(
                {"label": page.get("name") or str(page_id), "value": str(page_id)}
            )

        source_key = str(source.get(CONF_SKIDDLE_API_KEY) or "").strip()
        names: dict[str, dict[str, str]] = {}
        if source_key:
            try:
                names = await client.async_skiddle_venue_names(
                    source_key,
                    [str(v) for v in source.get(CONF_SKIDDLE_VENUE_IDS) or []],
                )
            except ApiError as err:
                _LOGGER.warning("Could not resolve Skiddle venue names: %s", err)

        skiddle_genres = await self._fetch_skiddle_genres(client, source_key)
        skiddle_genre_options = [
            {"label": genre["name"], "value": genre["id"]}
            for genre in skiddle_genres
        ]
        venue_options = []
        for venue_id in source.get(CONF_SKIDDLE_VENUE_IDS) or []:
            info = names.get(str(venue_id)) or {}
            label = info.get("name") or str(venue_id)
            if info.get("town"):
                label = f"{label} ({info['town']})"
            venue_options.append({"label": label, "value": str(venue_id)})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_RADIUS_MILES,
                        default=source[CONF_RADIUS_MILES],
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=500,
                            step=1,
                            unit_of_measurement=UNITS,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_GENRE,
                        default=genre_default,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=genre_options,
                            mode=SelectSelectorMode.DROPDOWN,
                            multiple=False,
                        )
                    ),
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=source[CONF_SCAN_INTERVAL],
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=30,
                            max=1440,
                            step=30,
                            unit_of_measurement="min",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_FATSOMA_PAGE_IDS,
                        default=list(source.get(CONF_FATSOMA_PAGE_IDS) or []),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=page_options,
                            mode=SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    ),
                    vol.Optional(
                        CONF_FATSOMA_SEARCH,
                        default=str(source.get(CONF_FATSOMA_SEARCH) or ""),
                    ): TextSelector(),
                    vol.Optional(
                        CONF_SKIDDLE_API_KEY,
                        default=str(source.get(CONF_SKIDDLE_API_KEY) or ""),
                    ): API_KEY_SELECTOR,
                    vol.Optional(
                        CONF_SKIDDLE_VENUE_IDS,
                        default=list(source.get(CONF_SKIDDLE_VENUE_IDS) or []),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=venue_options,
                            mode=SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    ),
                    vol.Optional(
                        CONF_SKIDDLE_GENRES,
                        default=list(source.get(CONF_SKIDDLE_GENRES) or []),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=skiddle_genre_options,
                            mode=SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    ),
                    vol.Optional(
                        CONF_SKIDDLE_SEARCH,
                        default=str(source.get(CONF_SKIDDLE_SEARCH) or ""),
                    ): TextSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_fatsoma_pages(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Manage the options: pick pages from a Fatsoma search."""
        errors: dict[str, str] = {}
        client = self._make_client()

        if user_input is not None:
            pending = dict(self._pending or {})
            base = list(pending.get(CONF_FATSOMA_PAGE_IDS) or [])
            selected = list(user_input.get(CONF_FATSOMA_PAGE_IDS) or [])
            merged = list(dict.fromkeys(base + selected))
            pending[CONF_FATSOMA_PAGE_IDS] = merged
            self._pending = pending
            return await self.async_step_init()

        pages = await client.async_search_fatsoma_pages(self._search_query)
        results = [
            {"label": page["name"], "value": page["id"]}
            for page in pages
            if page.get("id")
        ]
        if not results:
            errors["base"] = "no_pages_found"

        base = list((self._pending or {}).get(CONF_FATSOMA_PAGE_IDS) or [])
        result_ids = {item["value"] for item in results}
        default = [page_id for page_id in base if page_id in result_ids]

        return self.async_show_form(
            step_id="fatsoma_pages",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_FATSOMA_PAGE_IDS,
                        default=default,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=results,
                            mode=SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_skiddle_venues(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Manage the options: pick venues from a Skiddle search."""
        errors: dict[str, str] = {}
        client = self._make_client()
        pending = dict(self._pending or {})

        if user_input is not None:
            base = list(pending.get(CONF_SKIDDLE_VENUE_IDS) or [])
            selected = list(user_input.get(CONF_SKIDDLE_VENUE_IDS) or [])
            pending[CONF_SKIDDLE_VENUE_IDS] = list(dict.fromkeys(base + selected))
            self._pending = pending
            return await self.async_step_init()

        api_key = str(pending.get(CONF_SKIDDLE_API_KEY) or "").strip()
        results: list[dict[str, str]] = []
        if not api_key:
            errors["base"] = "skiddle_key_required"
        else:
            try:
                found = await client.async_search_skiddle_venues(
                    api_key, self._search_query
                )
            except ApiError as err:
                errors["base"] = err.reason
            else:
                results = [
                    {
                        "label": (
                            f"{venue['name']} ({venue['town']})"
                            if venue.get("town")
                            else venue["name"]
                        ),
                        "value": venue["id"],
                    }
                    for venue in found
                    if venue.get("id")
                ]
                if not results:
                    errors["base"] = "no_venues_found"

        base = list(pending.get(CONF_SKIDDLE_VENUE_IDS) or [])
        result_ids = {item["value"] for item in results}
        default = [venue_id for venue_id in base if venue_id in result_ids]

        return self.async_show_form(
            step_id="skiddle_venues",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SKIDDLE_VENUE_IDS,
                        default=default,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=results,
                            mode=SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    ),
                }
            ),
            errors=errors,
        )