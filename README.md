# Vehicle Tracking System

A Streamlit app that lets **Intergulf** share a live tracking link with their customers (e.g. **DHL**), so the customer can see where the Intergolf vehicle handling their job is at any time — without giving them access to Tenderd directly.

**Production URL:** https://track-with-tenderd.streamlit.app/
**Shareable deep-link format:** `https://track-with-tenderd.streamlit.app/?device_id=<DEVICE_ID>`

---

## Why this exists (context)

Intergolf runs vehicles on behalf of multiple customers, and the assignment of "which vehicle is on which customer's job" changes often. When DHL (or any other Intergolf customer) wants visibility into the vehicle running *their* shipment, Intergolf needs a way to:

1. Decide *this* specific vehicle is the one DHL should see.
2. Decide *from when* it should be visible (usually the moment the job starts).
3. Share a single URL with DHL that just works — no login, no Tenderd access.
4. Pull that vehicle off the share later, once the job is over.

This app is the customer-facing surface of that flow. The decision of *which vehicles are currently shared* is **not** managed here — it's managed by Intergolf in a spreadsheet, glued to this app by an n8n workflow.

---

## End-to-end flow

There are two people in the loop: **the Intergolf operator** (manages the list) and **the customer** (consumes the link).

### Intergolf operator — managing the shared list

1. Operator opens **Intergolf's fleet spreadsheet** (referenced from inside the n8n workflow below — *do not* hardcode it elsewhere; treat n8n as the source of truth).
2. The sheet has one row per vehicle Intergolf operates, with at least:
   - `device_id` — the Tenderd device identifier.
   - `plate_number` — the human-readable plate.
   - `time_added` — the moment from which the vehicle should start being visible to the customer (this also becomes the lower bound of the location history the customer sees).
   - Plus whatever column the n8n workflow uses to mark a row as "active / currently shared". Check the workflow node configuration if you need the exact column name.
3. To **start sharing** a vehicle: the operator marks it active in the sheet and sets `time_added` to roughly the job start time.
4. To **stop sharing**: the operator un-marks the row. The vehicle disappears from the dropdown (and any existing shareable link stops resolving) on the app's next webhook refresh.

### Customer (e.g. DHL) — consuming the link

1. Operator copies the share URL from the app — either by selecting the vehicle and clicking **Copy link**, or by constructing `…/?device_id=<id>` directly.
2. Operator sends it to the customer (email, Slack, WhatsApp — it's just a URL).
3. Customer opens the URL. The app:
   - Picks up `device_id` from the query string and pre-selects that vehicle.
   - Shows the vehicle's path from `time_added` until *now*, with the truck icon at the current location and a heading-aware directional peak.
   - Updates "Last Updated" each time the page is refreshed.
4. If the operator later removes the vehicle from the list, opening the same link will fall back to whatever the first vehicle in the list is (or show "No vehicles" if the list is empty). The vehicle simply stops being accessible.

### What happens under the hood when the link is opened

```
        ┌────────────────────────────────────────────────────────────────┐
        │  Customer (DHL) browser                                        │
        │  https://track-with-tenderd.streamlit.app/?device_id=…         │
        └────────────────────────────────────────────────────────────────┘
                                  │
                                  │ 1. page load
                                  ▼
        ┌────────────────────────────────────────────────────────────────┐
        │  Streamlit app (this repo)                                     │
        │                                                                │
        │  fetch_shared_vehicles()  ─── GET ──▶  n8n webhook             │
        │                                                                │
        │  (then for the selected device_id)                             │
        │  fetch_device_history()   ─── GET ──▶  Tenderd /histories      │
        └────────────────────────────────────────────────────────────────┘
                       │                                  │
                       │                                  │
                       ▼                                  ▼
        ┌──────────────────────────────┐   ┌──────────────────────────────┐
        │  n8n workflow                │   │  Tenderd telematics API      │
        │  • triggered by the webhook  │   │  • returns GPS pings between │
        │  • reads Intergolf's sheet   │   │    time_added and now        │
        │  • filters to active rows    │   │  • paginated                 │
        │  • returns [{device_id,      │   └──────────────────────────────┘
        │    plate_number, time_added}]│
        └──────────────────────────────┘
```

The webhook response is cached in Streamlit for **5 minutes** (`@st.cache_data(ttl=300)`). The sidebar **Refresh Data** button calls `st.cache_data.clear()` and forces an immediate re-fetch — useful right after an operator updates the sheet.

---

## Integrations

### 1. n8n workflow — source of the shared-vehicle list

The list of vehicles currently visible in the app is decided by an n8n workflow. The workflow:

- Is triggered by a GET webhook (called every time the Streamlit app fetches the list).
- Reads Intergolf's spreadsheet.
- Filters down to the rows the operator has marked active.
- Returns `[{device_id, plate_number, time_added}, …]` as JSON.

**Workflow URL:** https://tenderd-io.app.n8n.cloud/workflow/mI5H7h3aHDQ4bHAQ

Open the workflow when you need to:

- Find out which spreadsheet is being read, or change which one.
- Adjust which column marks a row as active.
- Rename / re-map columns before they reach the app.
- Rotate the webhook URL (after which **update `WEBHOOK_URL` in [`app.py`](app.py)** to match).

**Webhook contract.** The app expects a JSON array of objects with these fields:

```json
[
  {
    "device_id":    "ds5xDNtfTGrkdKebivub",
    "plate_number": "DXB /10808",
    "time_added":   "2025-12-03 8:00:00"
  }
]
```

Any extra fields are ignored. Rows missing any of these three fields are silently skipped.

### 2. Tenderd telematics API — vehicle GPS history

For each selected vehicle, the app calls Tenderd to get the location history from `time_added` up to now.

- **Base URL:** `https://telematics-svc-dr.tenderd.io`
- **Endpoint:** `GET /telematics/devices/{device_id}/histories`
- **Auth:** API key passed as the `key` query parameter; `accountid` and `geo` passed as headers.
- **Projection used:** `["fuel_level","ble_temperatures","speed","direction"]`
- **Pagination:** the app pages through results in 10,000-record chunks until an empty or short page is returned.
- **Where it's wired in code:** `TENDERD_API_BASE_URL`, `TENDERD_ACCOUNT_ID`, `TENDERD_GEO` constants in [`app.py`](app.py). The API key is read from secrets (`TENDERD_API_KEY`).

---

## Stack

- **Streamlit** — web framework, deployed on [Streamlit Community Cloud](https://share.streamlit.io/).
- **Folium / streamlit-folium** — Leaflet map embedded in the page.
- **pandas** — DataFrame for location history.
- **requests / pytz** — HTTP + UAE timezone conversion.
- **branca / jinja2** — used for the custom Leaflet "Re-center" control (transitive via folium).
- **Python 3.13** on Streamlit Cloud; 3.8+ locally.

All dependencies are pinned by name in [`requirements.txt`](requirements.txt).

---

## Repository layout

```
.
├── app.py                  # entire application (single-file Streamlit app)
├── requirements.txt        # Python dependencies
├── assets/
│   └── tenderd-logo.svg    # company lockup (embedded inline via base64)
├── .streamlit/
│   ├── config.toml         # forces light theme
│   ├── secrets.toml.example
│   └── secrets.toml        # local only — gitignored, holds TENDERD_API_KEY
├── .devcontainer/          # VS Code dev container config
├── .gitignore
└── README.md               # this file
```

---

## How the app works (function map)

Everything lives in [`app.py`](app.py). Top-to-bottom:

| Symbol | What it does |
|---|---|
| `_logo_data_uri()` | Reads `assets/tenderd-logo.svg` once and returns it as a base64 data URI so the logo can be embedded inline via `<img>`. Cached with `@st.cache_data`. |
| `render_logo(width, align, margin_bottom)` | Renders the logo via `st.markdown` + HTML. Used above the title and in the footer. |
| `RecenterControl(MacroElement)` | Custom Leaflet control injected into Folium. Shows a "Re-center" button in the top-right of the map; appears only when the user has panned/zoomed more than ~50 m or ~0.5 zoom levels away from the current vehicle position. Clicking re-runs `map.setView(target, defaultZoom)`. |
| `convert_to_uae_time(dt)` | Converts a (possibly tz-naive) datetime to `Asia/Dubai`. Naive datetimes are assumed UTC. |
| `fetch_shared_vehicles()` | `GET`s the n8n webhook, validates fields, returns `{device_id: {plate_number, time_added}}`. Cached for **5 minutes** (`@st.cache_data(ttl=300)`). The sidebar "Refresh Data" button calls `st.cache_data.clear()` to force a re-fetch. |
| `fetch_device_history(device_id, start_time)` | Pages through the Tenderd `/histories` endpoint, transforms each ping into a row (`timestamp` in UAE TZ, `latitude`, `longitude`, `speed`, `heading`, `ignition_status`, `distance`), returns a `pandas.DataFrame`. Has a single retry on connection/timeout errors. |
| `create_map(device_history_df, device_id, plate_number)` | Builds the Folium map. Centers on the current (latest) location at zoom 15. Adds: a blue polyline of the whole path, a green "START" label at the first ping, a truck-emoji-in-circle marker at the latest ping with a directional peak rotated by the `heading` value, periodic circle markers every 10 pings for context, and the `RecenterControl`. |

The bottom half of `app.py` is the page script (no functions):

1. Page config + light-theme baseline.
2. `fetch_shared_vehicles()` → populates the vehicle dropdown (plate number only; `device_id` shown as a grey monospace subtitle).
3. URL-query-param sync (`?device_id=…`) — both directions: a query param pre-selects on load, and changing the dropdown updates the URL so the page is bookmarkable / shareable.
4. **Share link** block — full `https://track-with-tenderd.streamlit.app/?device_id=…` URL with a "Copy link" button that uses `navigator.clipboard.writeText` (rendered as raw HTML via `streamlit.components.v1.html`).
5. Two-column metric row: **Plate Number** (with `device_id` subtitle) and **Tracking Since**.
6. `fetch_device_history()` → if empty, show a friendly warning.
7. Two-column layout: **Vehicle Path** (Folium map) on the left, **Statistics** on the right (Avg/Max speed, Tracking Duration, Last Updated in UAE TZ, then the last 5 pings as a small table — most-recent first — with a clickable `https://www.google.com/maps?q=<lat>,<lon>` link per row).
8. Expander: **View Last 24h Location History** — full table of the last 24 hours of pings.

---

## Configuration constants

| Name | Where | Notes |
|---|---|---|
| `WEBHOOK_URL` | `app.py` | n8n webhook for the shared-vehicle list. |
| `TENDERD_API_BASE_URL` | `app.py` | Currently the DR endpoint `telematics-svc-dr.tenderd.io`. |
| `TENDERD_ACCOUNT_ID` | `app.py` | Tenderd account scope. |
| `TENDERD_GEO` | `app.py` | Currently `"uae"`. |
| `TENDERD_API_KEY` | secrets | See **Secrets** below. |
| `[theme] base = "light"` | `.streamlit/config.toml` | Forces light mode regardless of the user's OS theme. |

---

## Secrets

The only secret is `TENDERD_API_KEY`. The app first tries `st.secrets["TENDERD_API_KEY"]`, then falls back to the `TENDERD_API_KEY` environment variable.

### Local

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit the file:
# TENDERD_API_KEY = "your_actual_api_key_here"
```

`.streamlit/secrets.toml` is gitignored.

### Streamlit Community Cloud

App dashboard → **Settings → Secrets** → paste:

```toml
TENDERD_API_KEY = "your_actual_api_key_here"
```

The app auto-restarts.

---

## Run locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then add your key
streamlit run app.py
```

Open http://localhost:8501. Deep-link to a specific vehicle with `?device_id=<id>`.

A dev container config is provided under `.devcontainer/` for VS Code / GitHub Codespaces.

---

## Deployment

The app is deployed on **Streamlit Community Cloud** and auto-redeploys on push to `main`. Steps to deploy a fresh copy:

1. Connect the repo at https://share.streamlit.io/.
2. Point it at `app.py` on `main`.
3. Add `TENDERD_API_KEY` under app **Secrets**.
4. Save. The app builds and is reachable at `https://<app-name>.streamlit.app/`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Dropdown is empty | n8n returned no active rows, or the webhook URL has rotated. | Open the [n8n workflow](https://tenderd-io.app.n8n.cloud/workflow/mI5H7h3aHDQ4bHAQ) → confirm it is **Active** (toggle top-right) and that a test execution returns a non-empty array. If the webhook URL changed, update `WEBHOOK_URL` in `app.py`. |
| Vehicle disappeared from the dropdown | Operator un-marked it in the sheet, or the row was removed. | Expected — confirm with the operator. If unexpected, check the sheet directly via the workflow. |
| A vehicle the operator just added isn't showing yet | 5-minute webhook cache. | Click **Refresh Data** in the sidebar — calls `st.cache_data.clear()` and re-runs the webhook immediately. |
| `TENDERD_API_KEY not found` | Secret missing. | Add it to `.streamlit/secrets.toml` locally or to **Secrets** in Streamlit Cloud. |
| "No location history is available for this vehicle" | Tenderd API returned no pings between `time_added` and now (vehicle offline, wrong device id, etc.). | Sanity-check by calling Tenderd directly: `GET https://telematics-svc-dr.tenderd.io/telematics/devices/<device_id>/histories` with the same headers and a recent date range. |
| Customer says the map is "stuck" / not updating | Streamlit doesn't auto-poll. | Refreshing the page re-runs both webhook + Tenderd calls. The "Last Updated" stat reflects the most recent ping returned. |
| App shows in dark mode | `.streamlit/config.toml` missing or overridden. | Confirm the file exists with `[theme]` `base = "light"`. |

A quick webhook smoke test from the CLI (returns whatever n8n currently considers "active"):

```bash
curl -s "https://tenderd-io.app.n8n.cloud/webhook/89b4621a-5e8a-4a4b-a2ed-40f1aaf2e2cf" | head -200
```

---

## Glossary

- **Intergolf** — the operator of the vehicles; the one managing the spreadsheet.
- **Customer (e.g. DHL)** — the recipient of the share link; sees only the one vehicle the link points at.
- **Tenderd** — the telematics platform the vehicles report to; source of GPS data.
- **n8n workflow** — middleware that translates Intergolf's spreadsheet into the JSON the app expects.
- **`time_added`** — the timestamp Intergolf assigns when adding a vehicle to the share. Becomes the start of the history window the customer can see.
