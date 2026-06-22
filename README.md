# Vehicle Tracking System

A Streamlit app that visualizes the recent path of Tenderd vehicles on an interactive map. The list of currently-tracked vehicles is managed in an **n8n workflow** (start/stop sharing forms); the app reads that list via a webhook and fetches per-vehicle GPS history from the **Tenderd telematics API**.

**Production URL:** https://track-with-tenderd.streamlit.app/
**Shareable deep-link format:** `https://track-with-tenderd.streamlit.app/?device_id=<DEVICE_ID>`

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

## Integrations

### 1. n8n workflow — source of the shared-vehicle list

The list of vehicles currently being tracked is **not stored in this repo**. It is managed by an n8n workflow that exposes a GET webhook. The app polls that webhook (cached 5 min) and renders the results in the dropdown.

- **n8n workflow:** https://tenderd-io.app.n8n.cloud/workflow/mI5H7h3aHDQ4bHAQ
  Open this workflow to:
  - See / edit the start-sharing form (adds a vehicle to the list).
  - See / edit the stop-sharing form (removes a vehicle).
  - Inspect the underlying data store (currently a Google Sheet — referenced inside the workflow, **do not duplicate the link here**; treat n8n as the source of truth).
  - Update what fields the webhook returns.

- **Webhook contract.** The app expects a JSON array of objects with these fields:

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

- **Where it's wired in code:** `WEBHOOK_URL` constant near the top of [`app.py`](app.py). If the webhook URL ever rotates, update this constant.

### 2. Tenderd telematics API — vehicle GPS history

For each selected vehicle, the app calls Tenderd's telematics service to get the location history from `time_added` up to now.

- **Base URL:** `https://telematics-svc-dr.tenderd.io`
- **Endpoint:** `GET /telematics/devices/{device_id}/histories`
- **Auth:** API key passed as the `key` query parameter; account/geo passed as headers.
- **Projection used:** `["fuel_level","ble_temperatures","speed","direction"]`
- **Pagination:** the app pages through results in 10,000-record chunks until an empty / short page is returned.
- **Where it's wired in code:** `TENDERD_API_BASE_URL`, `TENDERD_ACCOUNT_ID`, `TENDERD_GEO` constants in [`app.py`](app.py). The API key is read from secrets (`TENDERD_API_KEY`).

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
| Dropdown is empty | n8n webhook returned no rows, or webhook URL has rotated. | Open the [n8n workflow](https://tenderd-io.app.n8n.cloud/workflow/mI5H7h3aHDQ4bHAQ) → check that it's **Active** (toggle top-right) and that the test execution returns a non-empty array. If the webhook URL changed, update `WEBHOOK_URL` in `app.py`. |
| `TENDERD_API_KEY not found` | Secret missing. | Add it to `.streamlit/secrets.toml` locally or to **Secrets** in Streamlit Cloud. |
| "No location history is available for this vehicle" | Tenderd API returned no pings between `time_added` and now (vehicle offline, device wrong, etc.). | Sanity-check by calling the endpoint directly: `GET https://telematics-svc-dr.tenderd.io/telematics/devices/<device_id>/histories` with the same headers and a recent date range. |
| App shows in dark mode | `.streamlit/config.toml` missing or overridden. | Confirm the file exists with `[theme]` `base = "light"`. |
| Long-running vehicle crashes the "Last 24h" table | Unlikely after the 24h-scoping fix, but a >24h-of-high-frequency vehicle could still grow large. | The table already scopes to 24h; if you raise that window, also replace the `column_config` formatters with custom pagination. |

A quick webhook smoke test from the CLI:

```bash
curl -s "https://tenderd-io.app.n8n.cloud/webhook/89b4621a-5e8a-4a4b-a2ed-40f1aaf2e2cf" | head -200
```

---

## Sharing / stop-sharing a vehicle

This app **does not** add or remove vehicles from the tracked list — that's done in the n8n workflow. To start or stop sharing a vehicle, open the [n8n workflow](https://tenderd-io.app.n8n.cloud/workflow/mI5H7h3aHDQ4bHAQ) and use the start/stop forms inside it. Within ~5 minutes (webhook cache TTL) the change is reflected in the app; clicking **Refresh Data** in the sidebar forces an immediate refetch.
