# Gig Finder for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)

**Gig Finder** watches the live music listings around your home and feeds them into Home Assistant as sensors and a calendar — so you can see what's on, when, and get notified the moment a ticket goes on sale.

It pulls from three sources and merges the results into one deduplicated feed:

| Source | What it covers | Requires API key? |
|---|---|---|
| **Ticketmaster** Discovery API | Global events near your home, radius + optional genre | Yes |
| **Fatsoma** | UK venues & promoters gig listings | No |
| **Skiddle** | UK venues & genre-tagged live events | Yes (free) |

## Features

- **Radius-based search** — finds music events around your Home Assistant location (configurable 1–500 miles).
- **Genre filter** — optionally restrict Ticketmaster results to a single music genre from the live genre list.
- **Venue watching (Fatsoma)** — watch specific Fatsoma pages (venues/promoters) for their gigs.
- **Venue watching (Skiddle)** — watch specific Skiddle venues, optionally filtered by genre.
- **Deduplication** — the same gig listed on multiple sources appears once.
- **Calendar integration** — all upcoming events in one Home Assistant calendar with `[TM]`/`[FS]`/`[SK]` source tags.
- **Rich sensors** — next event, next event venue, next event URL and booking link, and an upcoming-events summary.
- **Fully UI configured** — no YAML required; all options editable in *Options* after setup.

## Installation

### Via HACS (recommended)

1. Open HACS in your Home Assistant sidebar.
2. Go to **Integrations** → **⋮ → Custom repositories**.
3. Add `https://github.com/Thrasher2020/home-assistant-gigfinder` with category **Integration**.
4. Click **Explore & download repositories**, search for **Gig Finder**, and download it.
5. Restart Home Assistant.

### Manual

1. Copy the `custom_components/ticketmaster` folder into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

## Getting API keys

### Ticketmaster (required)

1. Sign up / log in at [developer.ticketmaster.com](https://developer.ticketmaster.com).
2. Create an app to get your **Consumer API key** (not the secret).
3. Use it during Gig Finder setup.

### Skiddle (optional — only if you want to watch Skiddle venues)

1. Visit [skiddle.com/api](https://api.skiddle.com/) and request an API key (free for low-volume personal use).
2. Enter it in the Gig Finder options.

### Fatsoma

No key needed — only a venue or promoter page name to follow.

## Setup

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Gig Finder**.
3. Enter your Ticketmaster API key.

Then open **Options** to tune everything:

| Option | Default | Description |
|---|---|---|
| Search radius | 50 mi | How far from home to search (1–500 mi) |
| Music genre | *All genres* | Optional Ticketmaster genre filter, from the live list |
| Refresh interval | 360 min | How often to fetch listings (min 30, max 1440) |
| Fatsoma pages | — | Multi-select of gigs to watch; search by venue/promoter name |
| Skiddle API key | — | Needed for Skiddle venue watching |
| Skiddle venues | — | Multi-select; search by venue name |
| Skiddle genres | — | Optional genre tag filter for the selected venues |

## Entities

| Entity | Type | Description |
|---|---|---|
| `sensor.next_event` | Sensor | Name of the next upcoming gig |
| `sensor.next_event_starts_at` | Sensor | Start time of the next upcoming gig |
| `sensor.next_event_venue` | Sensor | Venue (+ town) of the next upcoming gig |
| `sensor.next_event_url` | Sensor | Booking/ticket link for the next gig |
| `sensor.upcoming_events` | Sensor | Number of upcoming gigs, with an `events` attribute listing each one |
| `calendar.events` | Calendar | All upcoming gigs, tagged by source (`TM` / `FS` / `SK`) |

All sensors also expose the gig's **source** and **url** as attributes.

## Example automation — new gig nearby

```yaml
automation:
  - alias: "New gig notification"
    trigger:
      - platform: state
        entity_id: sensor.next_event
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.old_state is none or trigger.entity_id != 'sensor.next_event' }}"
    action:
      - service: notify.mobile_app_phone
        data:
          title: "Gig on!"
          message: "{{ states('sensor.next_event') }} at {{ states('sensor.next_event_venue') }} — {{ states('sensor.next_event_url') }}"
```

## Troubleshooting

- **No events found** — increase the radius, clear the genre filter, or check your Home Assistant location coordinates.
- **Rate limited** — Ticketmaster/Skiddle throttle free keys; raise the refresh interval.
- **Skiddle search requires a key** — enter your Skiddle API key *before* searching venues.
- Diagnostics — enable debug logging:

```yaml
logger:
  default: warning
  logs:
    custom_components.ticketmaster: debug
```

## License

Apache-2.0. See [LICENSE](LICENSE).