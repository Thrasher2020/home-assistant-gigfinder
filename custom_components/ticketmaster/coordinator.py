"""Ticketmaster Discovery API client and coordinator."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from aiohttp import ClientError, ClientResponseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    API_BASE_URL,
    CONF_FATSOMA_PAGE_IDS,
    CONF_GENRE,
    CONF_GENRE_ID,
    CONF_RADIUS_MILES,
    CONF_SCAN_INTERVAL,
    CONF_SKIDDLE_API_KEY,
    CONF_SKIDDLE_GENRES,
    CONF_SKIDDLE_VENUE_IDS,
    DOMAIN,
    FATSOMA_BASE_URL,
    FATSOMA_GIGS_CATEGORY_ID,
    SKIDDLE_API_BASE_URL,
)

_LOGGER = logging.getLogger(__name__)


class ApiError(Exception):
    """Raised when the Ticketmaster API returns an error we can act on."""

    def __init__(self, message: str, reason: str = "cannot_connect") -> None:
        """Initialize the error."""
        super().__init__(message)
        self.reason = reason


NETWORK_EXCEPTIONS = (ClientError, ClientResponseError, TimeoutError)


class TicketmasterApiClient:
    """Async client for the Ticketmaster Discovery API."""

    def __init__(self, hass: HomeAssistant, api_key: str) -> None:
        """Initialize the client."""
        self._hass = hass
        self._api_key = api_key
        self._session = async_get_clientsession(hass)

    async def async_request(
        self, *, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make a GET request to the Discovery API and return JSON."""
        url = f"{API_BASE_URL}/{path}"
        query = params or {}
        query["apikey"] = self._api_key

        try:
            response = await self._session.get(
                url,
                params=query,
                headers={"Accept": "application/json"},
            )
            if response.status == 401 or response.status == 403:
                raise ApiError("Invalid API key", reason="invalid_api_key")
            if response.status == 429:
                raise ApiError("Rate limited by Ticketmaster", reason="rate_limited")
            response.raise_for_status()
            return await response.json()
        except ApiError:
            raise
        except ClientError as err:
            raise ApiError(f"Request failed: {err}") from err
        except TimeoutError as err:
            raise ApiError("Request timed out") from err

    async def async_validate(self) -> None:
        """Validate the API key with a minimal request."""
        await self.async_request(
            path="events.json", params={"classificationName": "music", "size": 1}
        )

    async def async_get_genres(self) -> list[dict[str, str]]:
        """Return the music genres known to the API, sorted by name."""
        data = await self.async_request(
            path="classifications.json", params={"size": 200}
        )
        genres: dict[str, str] = {}
        for cls in data.get("_embedded", {}).get("classifications", []):
            segment = cls.get("segment") or {}
            if segment.get("name") != "Music":
                continue
            embedded = segment.get("_embedded") or {}
            for genre in embedded.get("genres", []):
                name = genre.get("name")
                genre_id = genre.get("id")
                if name and genre_id:
                    genres.setdefault(name, genre_id)
        return [
            {"name": name, "id": genre_id}
            for name, genre_id in sorted(genres.items())
        ]

    async def _async_fatsoma_request(
        self, path: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Make a GET request to the public Fatsoma API and return JSON."""
        url = f"{FATSOMA_BASE_URL}/{path}"
        try:
            response = await self._session.get(
                url,
                params=params,
                headers={"Accept": "application/json"},
            )
            if response.status == 429:
                raise ApiError("Rate limited by Fatsoma", reason="rate_limited")
            response.raise_for_status()
            return await response.json()
        except ApiError:
            raise
        except ClientError as err:
            raise ApiError(f"Fatsoma request failed: {err}") from err
        except TimeoutError as err:
            raise ApiError("Fatsoma request timed out") from err

    async def async_search_fatsoma_pages(
        self, query: str, limit: int = 25
    ) -> list[dict[str, str]]:
        """Search Fatsoma pages (venues/promoters) by name."""
        data = await self._async_fatsoma_request(
            "pages",
            {
                "filter[name][contains]": query,
                "page[number]": 1,
                "page[size]": limit,
            },
        )
        pages: list[dict[str, str]] = []
        for page in data.get("data", []):
            attrs = page.get("attributes") or {}
            name = attrs.get("name")
            if name:
                pages.append(
                    {
                        "id": page.get("id") or "",
                        "name": name,
                        "vanity": attrs.get("vanity-name") or "",
                    }
                )
        return pages

    async def async_get_fatsoma_page(self, page_id: str) -> dict[str, str]:
        """Return a single Fatsoma page's name, or an empty dict."""
        try:
            data = await self._async_fatsoma_request(f"pages/{page_id}", {})
        except ApiError:
            return {}
        page = data.get("data") or {}
        attrs = page.get("attributes") or {}
        name = attrs.get("name")
        if name:
            return {
                "id": page_id,
                "name": name,
                "vanity": attrs.get("vanity-name") or "",
            }
        return {}

    async def async_get_fatsoma_events(
        self, page_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Return upcoming gig events for the given Fatsoma page ids."""
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        all_events: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_id in page_ids:
            data = await self._async_fatsoma_request(
                "events",
                {
                    "filter[status]": "active",
                    "filter[categories.id]": FATSOMA_GIGS_CATEGORY_ID,
                    "filter[page.id]": page_id,
                    "filter[starts-at][gte]": now,
                    "include": "location,categories",
                    "page[number]": 1,
                    "page[size]": 100,
                    "sort": "starts-at-time",
                },
            )
            for event in self._parse_fatsoma_events(data):
                if event["id"] in seen:
                    continue
                seen.add(event["id"])
                all_events.append(event)
        return all_events

    @staticmethod
    def _parse_fatsoma_start(raw: str | None) -> datetime | None:
        """Parse a Fatsoma start timestamp into a timezone-aware datetime."""
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed

    def _parse_fatsoma_events(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Normalise Fatsoma JSON:API events into the shared event shape."""
        locations: dict[str, dict[str, Any]] = {}
        for item in data.get("included", []):
            if item.get("type") != "locations":
                continue
            attrs = item.get("attributes") or {}
            locations[item.get("id")] = {
                "name": attrs.get("name") or "Unknown venue",
                "city": attrs.get("city") or "",
            }

        events: list[dict[str, Any]] = []
        for event in data.get("data", []):
            attrs = event.get("attributes") or {}
            start = self._parse_fatsoma_start(attrs.get("starts-at"))
            if start is None:
                continue
            location_id = (
                ((event.get("relationships") or {}).get("location") or {})
                .get("data") or {}
            ).get("id")
            location = locations.get(location_id) if location_id else None
            location = location if location is not None else {}
            venue: dict[str, Any] = {"name": location.get("name", "Unknown venue")}
            if location.get("city"):
                venue["city"] = {"name": location["city"]}
            vanity = attrs.get("vanity-name") or ""
            events.append(
                {
                    "id": f"fatsoma:{event.get('id')}",
                    "name": attrs.get("name") or "Unknown event",
                    "url": f"https://www.fatsoma.com/e/{vanity}" if vanity else "",
                    "start": start,
                    "venue": venue,
                    "genre": None,
                    "lineup": [],
                    "on_sale": attrs.get("on-sale"),
                    "source": "fatsoma",
                }
            )
        return events

    async def _async_skiddle_request(
        self, path: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Make a GET request to the Skiddle API and return JSON."""
        url = f"{SKIDDLE_API_BASE_URL}/{path}"
        try:
            response = await self._session.get(url, params=params)
            if response.status == 403:
                raise ApiError("Invalid Skiddle API key", reason="invalid_api_key")
            if response.status == 429:
                raise ApiError("Rate limited by Skiddle", reason="rate_limited")
            response.raise_for_status()
            return await response.json()
        except ApiError:
            raise
        except ClientError as err:
            raise ApiError(f"Skiddle request failed: {err}") from err
        except TimeoutError as err:
            raise ApiError("Skiddle request timed out") from err

    async def async_validate_skiddle_key(self, api_key: str) -> None:
        """Check a Skiddle API key is accepted."""
        await self._async_skiddle_request(
            "events/search/",
            {"api_key": api_key, "eventcode": "LIVE", "limit": 1, "offset": 0},
        )

    async def async_get_skiddle_genres(self, api_key: str) -> list[dict[str, str]]:
        """Return the Skiddle genre list, sorted by name."""
        data = await self._async_skiddle_request("genres/", {"api_key": api_key})
        if isinstance(data, list):
            results: list[Any] = data
        else:
            rows = data.get("results") or []
            if isinstance(rows, dict):
                results = rows.get("rows") or []
            else:
                results = rows
        genres: dict[str, str] = {}
        for item in results:
            if not isinstance(item, dict):
                continue
            genre_id = (
                item.get("genreid")
                or item.get("GenreID")
                or item.get("genre_id")
                or item.get("id")
            )
            name = item.get("name") or item.get("GenreName") or item.get("genre")
            if genre_id and name:
                genres.setdefault(str(genre_id), str(name))
        return [
            {"id": genre_id, "name": name}
            for genre_id, name in sorted(genres.items(), key=lambda kv: kv[1])
        ]

    async def async_search_skiddle_venues(
        self, api_key: str, query: str, limit: int = 25
    ) -> list[dict[str, str]]:
        """Discover Skiddle venues behind live gigs matching a keyword."""
        data = await self._async_skiddle_request(
            "events/search/",
            {
                "api_key": api_key,
                "eventcode": "LIVE",
                "keyword": query,
                "description": 1,
                "order": "trending",
                "limit": limit,
                "offset": 0,
            },
        )
        venues: dict[str, dict[str, str]] = {}
        for event in data.get("results", []):
            venue = event.get("venue") or {}
            venue_id = venue.get("id")
            name = venue.get("name")
            if not venue_id or not name:
                continue
            venues[str(venue_id)] = {
                "id": str(venue_id),
                "name": name,
                "town": venue.get("town") or "",
            }
        return list(venues.values())[:limit]

    async def async_skiddle_venue_names(
        self, api_key: str, venue_ids: list[str]
    ) -> dict[str, dict[str, str]]:
        """Resolve venue ids to names via a venue-scoped event search."""
        data = await self._async_skiddle_request(
            "events/search/",
            {
                "api_key": api_key,
                "eventcode": "LIVE",
                "venueid": ",".join(venue_ids),
                "description": 1,
                "order": "date",
                "limit": 100,
                "offset": 0,
            },
        )
        venues: dict[str, dict[str, str]] = {}
        for event in data.get("results", []):
            venue = event.get("venue") or {}
            venue_id = venue.get("id")
            name = venue.get("name")
            if not venue_id or not name:
                continue
            venues.setdefault(
                str(venue_id),
                {
                    "id": str(venue_id),
                    "name": name,
                    "town": venue.get("town") or "",
                },
            )
        return venues

    async def async_get_skiddle_events(
        self,
        api_key: str,
        venue_ids: list[str],
        genre_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return upcoming live-music events at the given Skiddle venues."""
        if not venue_ids:
            return []
        events: list[dict[str, Any]] = []
        venue_param = ",".join(venue_ids)
        genre_param = ",".join(genre_ids or [])
        min_date = datetime.now(ZoneInfo("Europe/London")).strftime("%Y-%m-%d")
        offset = 0
        for _ in range(5):
            params: dict[str, Any] = {
                "api_key": api_key,
                "eventcode": "LIVE",
                "venueid": venue_param,
                "description": 1,
                "order": "date",
                "minDate": min_date,
                "limit": 100,
                "offset": offset,
            }
            if genre_param:
                params["g"] = genre_param
            data = await self._async_skiddle_request("events/search/", params)
            results = data.get("results", [])
            events.extend(self._parse_skiddle_events(results))
            paginate = data.get("paginate") or {}
            total = int(paginate.get("results") or len(results) or 0)
            if len(results) < 100 or offset + len(results) >= total:
                break
            offset += len(results)
        return events

    @staticmethod
    def _parse_skiddle_start(raw: str | None) -> datetime | None:
        """Parse a Skiddle start timestamp into a timezone-aware datetime."""
        if not raw:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"):
            try:
                parsed = datetime.strptime(raw, fmt)
                break
            except (ValueError, TypeError):
                continue
        else:
            try:
                parsed = datetime.fromisoformat(raw)
            except (ValueError, TypeError):
                return None
            if parsed.tzinfo is not None:
                return parsed
        return parsed.replace(tzinfo=ZoneInfo("Europe/London"))

    def _parse_skiddle_events(
        self, results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Normalise Skiddle events into the shared event shape."""
        events: list[dict[str, Any]] = []
        for event in results:
            start = self._parse_skiddle_start(event.get("startdate"))
            if start is None:
                continue
            venue = event.get("venue") or {}
            venue_out: dict[str, Any] = {"name": venue.get("name") or "Unknown venue"}
            town = venue.get("town") or ""
            if town:
                venue_out["city"] = {"name": town}
            artists = [
                str(artist.get("name"))
                for artist in (event.get("artists") or [])
                if artist.get("name")
            ]
            genres = [
                str(genre.get("genre"))
                for genre in (event.get("genres") or [])
                if genre.get("genre")
            ]
            events.append(
                {
                    "id": f"skiddle:{event.get('id')}",
                    "name": event.get("eventname") or "Unknown event",
                    "url": event.get("link") or "",
                    "start": start,
                    "venue": venue_out,
                    "genre": genres[0] if genres else None,
                    "lineup": artists,
                    "on_sale": None,
                    "source": "skiddle",
                }
            )
        return events

    async def async_get_events(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_miles: int,
        genre: str | None,
        genre_id: str | None,
    ) -> list[dict[str, Any]]:
        """Return upcoming music events near the given coordinate."""
        params: dict[str, Any] = {
            "latlong": f"{latitude},{longitude}",
            "radius": radius_miles,
            "unit": "miles",
            "classificationName": "music",
            "startDateTime": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sort": "date,asc",
            "size": 100,
        }
        if genre_id:
            params["genreId"] = genre_id
        elif genre:
            params["classificationName"] = ["music", genre]

        data = await self.async_request(path="events.json", params=params)
        embedded = data.get("_embedded", {})

        events = []
        for event in embedded.get("events", []):
            start = self._parse_start_datetime(event)
            if start is None:
                continue
            venue = self._first_venue(event)
            classification = self._first_classification(event)
            events.append(
                {
                    "id": event.get("id"),
                    "name": event.get("name"),
                    "url": event.get("url"),
                    "start": start,
                    "venue": venue,
                    "genre": classification,
                    "lineup": self._lineup(event),
                    "on_sale": self._is_on_sale(event),
                    "source": "ticketmaster",
                }
            )
        return events

    def _parse_start_datetime(self, event: dict[str, Any]) -> datetime | None:
        """Parse the event start datetime into a timezone-aware datetime."""
        dates = event.get("dates", {})
        start = dates.get("start", {})
        raw = start.get("dateTime")
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
        except (ValueError, TypeError):
            return None

    def _first_venue(self, event: dict[str, Any]) -> dict[str, Any] | None:
        embedded = event.get("_embedded", {})
        venues = embedded.get("venues") or []
        if venues:
            return venues[0]
        return None

    def _first_classification(self, event: dict[str, Any]) -> dict[str, Any] | None:
        classifications = event.get("classifications") or []
        for cls in classifications:
            if cls.get("segment", {}).get("name") == "Music":
                return cls.get("genre") or {}
            genre = cls.get("genre")
            if genre:
                return genre or {}
        return None

    def _lineup(self, event: dict[str, Any]) -> list[str]:
        embedded = event.get("_embedded", {})
        return [
            str(attraction.get("name"))
            for attraction in (embedded.get("attractions") or [])
            if attraction.get("name")
        ]

    def _is_on_sale(self, event: dict[str, Any]) -> bool | None:
        """Return whether the event's tickets are currently on sale."""
        sales = event.get("sales", {})
        public = sales.get("public") or {}
        start_date = public.get("startDateTime")
        end_date = public.get("endDateTime")
        if not start_date:
            return None
        now = datetime.now(UTC)
        try:
            start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            end = (
                datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                if end_date
                else None
            )
        except (ValueError, TypeError):
            return None
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end is not None and end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        if now < start:
            return False
        if end is not None and now > end:
            return False
        return True


class TicketmasterCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Fetch Ticketmaster events for the configured radius and genre."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self._entry = entry
        self._client = TicketmasterApiClient(hass, entry.data["api_key"])

        options = dict(entry.options)
        scan_interval = int(options.get(CONF_SCAN_INTERVAL, 360)) or 360
        scan_interval = max(30, min(1440, scan_interval))

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )

    @property
    def radius_miles(self) -> int:
        """Return the configured search radius in miles."""
        options = dict(self._entry.options)
        return int(options.get(CONF_RADIUS_MILES, 50))

    @property
    def genre(self) -> str | None:
        """Return the configured genre name, if any."""
        options = dict(self._entry.options)
        genre = str(options.get(CONF_GENRE, "") or "").strip()
        return genre or None

    @property
    def genre_id(self) -> str | None:
        """Return the configured music genre ID, if any."""
        options = dict(self._entry.options)
        genre_id = str(options.get(CONF_GENRE_ID, "") or "").strip()
        return genre_id or None

    @property
    def fatsoma_page_ids(self) -> list[str]:
        """Return the configured Fatsoma page IDs."""
        options = dict(self._entry.options)
        return list(options.get(CONF_FATSOMA_PAGE_IDS) or [])

    @property
    def skiddle_api_key(self) -> str | None:
        """Return the configured Skiddle API key, if any."""
        options = dict(self._entry.options)
        api_key = str(options.get(CONF_SKIDDLE_API_KEY) or "").strip()
        return api_key or None

    @property
    def skiddle_venue_ids(self) -> list[str]:
        """Return the configured Skiddle venue IDs."""
        options = dict(self._entry.options)
        return list(options.get(CONF_SKIDDLE_VENUE_IDS) or [])

    @property
    def skiddle_genre_ids(self) -> list[str]:
        """Return the configured Skiddle genre IDs."""
        options = dict(self._entry.options)
        return [str(genre) for genre in (options.get(CONF_SKIDDLE_GENRES) or [])]

    def _dedupe_events(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Drop duplicate events sharing a start, name and venue."""
        seen: set[tuple[str, str, str]] = set()
        deduped: list[dict[str, Any]] = []
        for event in events:
            name = str(event.get("name") or "").lower().strip()
            venue = str((event.get("venue") or {}).get("name") or "").lower().strip()
            key = (event["start"].isoformat(), name, venue)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(event)
        return deduped

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch events from Ticketmaster, then optionally Fatsoma/Skiddle."""
        lat = self.hass.config.latitude
        lon = self.hass.config.longitude
        try:
            ticketmaster = await self._client.async_get_events(
                latitude=lat,
                longitude=lon,
                radius_miles=self.radius_miles,
                genre=self.genre,
                genre_id=self.genre_id,
            )
        except ApiError as err:
            raise UpdateFailed(str(err)) from err

        events = list(ticketmaster)
        if page_ids := self.fatsoma_page_ids:
            try:
                events.extend(await self._client.async_get_fatsoma_events(page_ids))
            except ApiError as err:
                _LOGGER.warning(
                    "Fatsoma events unavailable, continuing with the other sources: %s",
                    err,
                )
        if (skiddle_key := self.skiddle_api_key) and self.skiddle_venue_ids:
            try:
                events.extend(
                    await self._client.async_get_skiddle_events(
                        skiddle_key,
                        self.skiddle_venue_ids,
                        self.skiddle_genre_ids,
                    )
                )
            except ApiError as err:
                _LOGGER.warning(
                    "Skiddle events unavailable, continuing with the other sources: %s",
                    err,
                )

        try:
            events.sort(key=lambda event: event["start"])
        except (KeyError, TypeError):
            pass
        return self._dedupe_events(events)