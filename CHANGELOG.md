# Changelog

All notable changes to the Gig Finder integration are documented here.

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
