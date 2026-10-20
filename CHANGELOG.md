# Changelog

All notable changes to the Gig Finder integration are documented here.

## [0.2.1] - 2026-10-20

### Fixed
- The Skiddle time zone is no longer built with `ZoneInfo(...)` inside the
  event loop; it is resolved once with `async_get_time_zone()` and passed into
  the parsing helpers, so a refresh no longer blocks the event loop.
- The "next event" sensors and the `upcoming_events` attribute now compare
  timezone-aware datetimes against `dt_util.utcnow()` instead of stripping the
  offsets from both sides. On installations not running in UTC they were off
  by the UTC offset, which could show a past gig as the next one or skip an
  upcoming one.
- A Fatsoma error while searching pages in the options flow (network failure
  or rate limit) now shows an error on the form instead of ending the flow
  with an unknown error.
- The Gig Finder calendar is now a `CoordinatorEntity`, so it refreshes when
  the coordinator updates instead of keeping its previous state.

## [0.2.0] - 2026-10-01

### Added
- Select multiple music genres for the Ticketmaster search. Selected genres
  are combined as "any match", so an event tagged with any of them is kept.

### Fixed
- Ticketmaster search now paginates through the API (up to the 1000-item deep
  paging limit) instead of fetching only the first 100 events, extending the
  search horizon from roughly a week to roughly two months in busy areas.
- Genre filtering is now applied client-side against each event's genre, so
  multiple genres combine correctly. The API's comma-separated genreId
  parameter was not honoured.
- Genre selection is stored as genre IDs and existing single-genre
  configurations are migrated automatically.

## [0.1.1] - 2026-09-17

### Fixed
- HACS and hassfest validation fixes (manifest key ordering, hacs.json).

## [0.1.0] - 2026-09-16

### Added
- Initial release: Ticketmaster Discovery API search near your home, Fatsoma
  page watching, Skiddle venue watching, deduplicated events across sources,
  and calendar and sensor platforms.
