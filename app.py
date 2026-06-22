import base64
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta
import requests
import pytz
from branca.element import MacroElement
from jinja2 import Template


LOGO_PATH = Path(__file__).parent / "assets" / "tenderd-logo.svg"


@st.cache_data
def _logo_data_uri() -> str:
    """Load the Tenderd logo as a base64 data URI for inline <img> embedding."""
    encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode()
    return f"data:image/svg+xml;base64,{encoded}"


def render_logo(width: int = 200, align: str = "left", margin_bottom: int = 8) -> None:
    """Render the Tenderd logo at the given width/alignment."""
    st.markdown(
        f"""
        <div style="text-align:{align};margin-bottom:{margin_bottom}px;">
            <img src="{_logo_data_uri()}" width="{width}"
                 alt="Tenderd" style="display:inline-block;" />
        </div>
        """,
        unsafe_allow_html=True,
    )


class RecenterControl(MacroElement):
    """Leaflet control button that re-centers the map on a target point.
    Hidden when the map is already centered on the target, shown after pan/zoom."""

    _template = Template("""
        {% macro script(this, kwargs) %}
            (function() {
                var map = {{ this._parent.get_name() }};
                var target = L.latLng({{ this.lat }}, {{ this.lon }});
                var defaultZoom = {{ this.zoom }};
                var ctrl = L.control({position: 'topright'});
                ctrl.onAdd = function() {
                    var div = L.DomUtil.create('div', '');
                    div.style.cssText = 'background:white;' +
                        'border:2px solid rgba(0,0,0,0.2);border-radius:4px;' +
                        'cursor:pointer;display:none;box-shadow:0 1px 3px rgba(0,0,0,0.2);' +
                        'background-clip:padding-box;';
                    div.innerHTML = '<a href="#" title="Re-center on vehicle" ' +
                        'style="display:block;padding:6px 12px;font-size:12px;' +
                        'font-weight:600;color:#333;text-decoration:none;' +
                        'white-space:nowrap;font-family:sans-serif;line-height:1;">' +
                        'Re-center</a>';
                    L.DomEvent.disableClickPropagation(div);
                    L.DomEvent.on(div, 'click', function(e) {
                        L.DomEvent.preventDefault(e);
                        map.setView(target, defaultZoom);
                    });
                    return div;
                };
                ctrl.addTo(map);
                var el = ctrl.getContainer();
                function check() {
                    var c = map.getCenter();
                    var dist = c.distanceTo(target);
                    var zoomDiff = Math.abs(map.getZoom() - defaultZoom);
                    if (dist > 50 || zoomDiff > 0.5) {
                        el.style.display = 'block';
                    } else {
                        el.style.display = 'none';
                    }
                }
                map.on('moveend zoomend', check);
            })();
        {% endmacro %}
    """)

    def __init__(self, lat, lon, zoom):
        super().__init__()
        self._name = "RecenterControl"
        self.lat = lat
        self.lon = lon
        self.zoom = zoom

# Configure page
st.set_page_config(
    page_title="Vehicle Tracking System",
    page_icon="🚛",
    layout="wide"
)

# Webhook URL for fetching shared vehicles
WEBHOOK_URL = "https://tenderd-io.app.n8n.cloud/webhook/89b4621a-5e8a-4a4b-a2ed-40f1aaf2e2cf"

# Tenderd API Configuration
TENDERD_API_BASE_URL = "https://telematics-svc-dr.tenderd.io"
TENDERD_ACCOUNT_ID = "Xv7pB1sVxPp0ioTyqYo7"
TENDERD_GEO = "uae"

# UAE Timezone (UTC+4)
UAE_TZ = pytz.timezone('Asia/Dubai')

# Get API key from secrets or environment variable
try:
    TENDERD_API_KEY = st.secrets["TENDERD_API_KEY"]
except (FileNotFoundError, KeyError):
    # Fallback to environment variable if secrets file doesn't exist
    import os
    TENDERD_API_KEY = os.getenv("TENDERD_API_KEY", "")
    if not TENDERD_API_KEY:
        st.error("⚠️ TENDERD_API_KEY not found. Please set it in .streamlit/secrets.toml or as an environment variable.")
        st.stop()

def convert_to_uae_time(dt):
    """
    Convert a datetime object to UAE time (UTC+4).
    If the datetime is naive (no timezone), assumes it's UTC.
    """
    if dt is None:
        return None

    # If datetime is timezone-naive, assume it's UTC
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)

    # Convert to UAE timezone
    return dt.astimezone(UAE_TZ)

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_shared_vehicles():
    """
    Fetch shared vehicles data from webhook.
    Returns a dictionary in the format: {device_id: {plate_number, time_added}}
    """
    try:
        # Fetch data from webhook
        response = requests.get(WEBHOOK_URL, timeout=10)
        response.raise_for_status()

        # Parse JSON response
        vehicles_data = response.json()

        # Validate response is a list
        if not isinstance(vehicles_data, list):
            raise ValueError(f"Expected webhook to return a list, got {type(vehicles_data)}")

        # Convert list to dictionary format
        shared_vehicles = {}
        for item in vehicles_data:
            # Validate required fields
            if not all(key in item for key in ['device_id', 'plate_number', 'time_added']):
                st.warning(f"Skipping item with missing fields: {item}")
                continue

            # Skip rows with empty/null data
            device_id = item.get('device_id')
            plate_number = item.get('plate_number')
            time_added = item.get('time_added')

            if not device_id or not plate_number or not time_added:
                continue

            # Convert to strings and strip whitespace
            device_id = str(device_id).strip()
            shared_vehicles[device_id] = {
                "plate_number": str(plate_number).strip(),
                "time_added": str(time_added).strip()
            }

        if not shared_vehicles:
            st.warning("No valid vehicle data found from webhook")

        return shared_vehicles

    except requests.RequestException as e:
        st.error(f"Network error while fetching webhook data: {str(e)}")
        return {}
    except ValueError as e:
        st.error(f"Data format error: {str(e)}")
        return {}
    except Exception as e:
        st.error(f"Unexpected error fetching data from webhook: {str(e)}")
        return {}

def fetch_device_history(device_id, start_time):
    """
    Fetch real device history data from Tenderd API with pagination.
    """
    try:
        # Parse start time - handle multiple formats
        if isinstance(start_time, str):
            # Try different datetime formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"]:
                try:
                    start_dt = datetime.strptime(start_time.strip(), fmt)
                    break
                except ValueError:
                    continue
            else:
                # If no format matches, try a simple parse
                try:
                    start_dt = pd.to_datetime(start_time)
                except:
                    st.error(f"Could not parse start time: {start_time}")
                    return pd.DataFrame()
        else:
            start_dt = start_time

        # Set end time to now
        end_dt = datetime.now()

        # Format dates for API (ISO format with timezone)
        start_date_str = start_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        end_date_str = end_dt.strftime("%Y-%m-%dT%H:%M:%S.999Z")

        # Build API URL
        url = f"{TENDERD_API_BASE_URL}/telematics/devices/{device_id}/histories"

        # Set headers
        headers = {
            "accept": "*/*",
            "accountid": TENDERD_ACCOUNT_ID,
            "geo": TENDERD_GEO,
            "content-type": "application/json"
        }

        # Pagination setup
        page = 1
        limit = 10000
        all_data = []

        # Fetch all pages
        while True:
            params = {
                "start_date": start_date_str,
                "end_date": end_date_str,
                "geo": TENDERD_GEO,
                "projection": '["fuel_level","ble_temperatures","speed","direction"]',
                "key": TENDERD_API_KEY,
                "allData": "true",
                "page": str(page),
                "limit": str(limit)
            }

            # Make API request with one retry on transient connection failures
            last_exc = None
            for attempt in range(2):
                try:
                    response = requests.get(url, params=params, headers=headers, timeout=30)
                    response.raise_for_status()
                    last_exc = None
                    break
                except (requests.ConnectionError, requests.Timeout) as e:
                    last_exc = e
            if last_exc is not None:
                raise last_exc

            # Parse response
            response_data = response.json()

            # Handle response structure - the /histories endpoint returns {data: [...]}
            if isinstance(response_data, dict) and "data" in response_data:
                data = response_data["data"]
            else:
                data = response_data

            # If no data in this page, we're done
            if not data or len(data) == 0:
                break

            # Add data from this page
            all_data.extend(data)

            # If we got fewer records than the limit, we've reached the last page
            if len(data) < limit:
                break

            # Move to next page
            page += 1

        if not all_data or len(all_data) == 0:
            st.warning(f"No history data found for device {device_id}")
            return pd.DataFrame()

        # Transform API response to DataFrame format
        history = []
        for item in all_data:
            # Extract coordinates from location object
            coordinates = item.get("location", {}).get("coordinates", [])
            if len(coordinates) >= 2:
                latitude = coordinates[0]
                longitude = coordinates[1]
            else:
                continue

            # Parse datetime and convert to UAE time
            dt = pd.to_datetime(item.get("datetime"))
            dt_uae = convert_to_uae_time(dt)

            history.append({
                "device_id": device_id,
                "timestamp": dt_uae,
                "latitude": latitude,
                "longitude": longitude,
                "speed": item.get("speed", 0),
                "heading": item.get("direction", 0),
                "ignition_status": item.get("ignition_status", False),
                "distance": item.get("distance", 0)
            })

        df = pd.DataFrame(history)

        if df.empty:
            st.warning(f"No valid location data for device {device_id}")

        return df

    except requests.RequestException as e:
        st.error(f"API error fetching device history: {str(e)}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error processing device history: {str(e)}")
        return pd.DataFrame()

def create_map(device_history_df, device_id, plate_number):
    """
    Create a Folium map with the vehicle's path.
    """
    if device_history_df.empty:
        st.warning("No location data available for this vehicle")
        return None

    # Center map on the current (latest) vehicle location
    last_row = device_history_df.iloc[-1]
    current_lat = last_row['latitude']
    current_lon = last_row['longitude']
    current_heading = float(last_row.get('heading', 0) or 0)
    default_zoom = 15

    m = folium.Map(
        location=[current_lat, current_lon],
        zoom_start=default_zoom,
        tiles="OpenStreetMap"
    )

    # Add path line
    coordinates = list(zip(
        device_history_df['latitude'],
        device_history_df['longitude']
    ))

    folium.PolyLine(
        coordinates,
        color='blue',
        weight=3,
        opacity=0.7,
        popup=f"{device_id} - {plate_number}"
    ).add_to(m)

    # Start marker — text label
    folium.Marker(
        [device_history_df.iloc[0]['latitude'], device_history_df.iloc[0]['longitude']],
        popup=f"Start: {device_history_df.iloc[0]['timestamp']}",
        icon=folium.DivIcon(
            icon_size=(60, 24),
            icon_anchor=(30, 12),
            html=(
                '<div style="font-size:12px;font-weight:700;color:#fff;'
                'background:#2e7d32;padding:2px 8px;border-radius:4px;'
                'border:1px solid #1b5e20;text-align:center;'
                'box-shadow:0 1px 3px rgba(0,0,0,0.3);">START</div>'
            )
        )
    ).add_to(m)

    # Current location marker — truck in circle with directional peak
    truck_html = (
        f'<div style="width:52px;height:62px;position:relative;'
        f'transform:rotate({current_heading}deg);transform-origin:26px 36px;">'
        # Directional peak (triangle pointing in heading direction)
        f'<div style="position:absolute;top:0;left:50%;'
        f'transform:translateX(-50%);width:0;height:0;'
        f'border-left:8px solid transparent;border-right:8px solid transparent;'
        f'border-bottom:12px solid #1f1f1f;"></div>'
        # Circle background with truck (counter-rotated to stay upright)
        f'<div style="position:absolute;top:10px;left:6px;width:40px;height:40px;'
        f'border-radius:50%;background:#ffffff;border:2px solid #1f1f1f;'
        f'display:flex;align-items:center;justify-content:center;'
        f'box-shadow:0 2px 6px rgba(0,0,0,0.35);">'
        f'<span style="font-size:22px;line-height:1;display:inline-block;'
        f'transform:rotate(-{current_heading}deg);">🚛</span>'
        f'</div>'
        f'</div>'
    )
    folium.Marker(
        [current_lat, current_lon],
        popup=f"Current: {last_row['timestamp']}<br>Heading: {current_heading:.0f}°",
        icon=folium.DivIcon(
            icon_size=(52, 62),
            icon_anchor=(26, 36),
            html=truck_html
        )
    ).add_to(m)

    # Add markers for every 10th point to show progression
    for idx in range(0, len(device_history_df), 10):
        row = device_history_df.iloc[idx]
        folium.CircleMarker(
            [row['latitude'], row['longitude']],
            radius=4,
            popup=f"Time: {row['timestamp']}<br>Speed: {row['speed']:.1f} km/h",
            color='darkblue',
            fill=True,
            fillColor='lightblue'
        ).add_to(m)

    # Re-center button (appears when user pans/zooms away from current location)
    m.add_child(RecenterControl(current_lat, current_lon, default_zoom))

    return m

# Fetch shared vehicles from webhook
with st.spinner("Loading vehicle data..."):
    SHARED_VEHICLES = fetch_shared_vehicles()

# Sidebar
with st.sidebar:
    st.header("About")
    st.info(
        "This system tracks vehicles that have been shared for monitoring. "
        "Select a vehicle from the dropdown to view its historical path."
    )

    st.markdown("### System Info")
    st.markdown(f"**Total Shared Vehicles:** {len(SHARED_VEHICLES)}")
    current_time_uae = datetime.now(UAE_TZ)
    st.markdown(f"**Last Updated:** {current_time_uae.strftime('%Y-%m-%d %H:%M:%S')} UAE")

    # Add refresh button
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# Main app
render_logo(width=260, align="left", margin_bottom=12)
st.title("Live Location Tracking")
st.markdown("---")

# Main content
if not SHARED_VEHICLES:
    st.warning("No vehicles are currently being shared for tracking.")
else:
    # Dropdown shows plate number; map back to device_id via lookup
    device_ids = list(SHARED_VEHICLES.keys())
    plate_to_device = {
        SHARED_VEHICLES[did]['plate_number']: did for did in device_ids
    }
    plate_options = [SHARED_VEHICLES[did]['plate_number'] for did in device_ids]

    # Check for device_id in query parameters
    query_params = st.query_params
    url_device_id = query_params.get("device_id", None)

    # Determine initial index based on URL parameter
    initial_index = 0
    if url_device_id and url_device_id in SHARED_VEHICLES:
        target_plate = SHARED_VEHICLES[url_device_id]['plate_number']
        if target_plate in plate_options:
            initial_index = plate_options.index(target_plate)

    selected_plate = st.selectbox(
        "Select a vehicle to track:",
        options=plate_options,
        index=initial_index
    )

    selected_device_id = plate_to_device[selected_plate]
    vehicle_info = SHARED_VEHICLES[selected_device_id]

    # Update URL query parameter when selection changes
    if query_params.get("device_id") != selected_device_id:
        st.query_params["device_id"] = selected_device_id

    # Display shareable link with copy-to-clipboard button
    share_url = f"https://track-with-tenderd.streamlit.app/?device_id={selected_device_id}"
    components.html(
        f"""
        <div style="display:flex;align-items:center;gap:8px;padding:10px 12px;
                    background:#e7f3fe;border-left:4px solid #1c83e1;border-radius:4px;
                    font-family:'Source Sans Pro',sans-serif;">
            <span style="font-size:14px;white-space:nowrap;">
                📋 <strong>Share this vehicle:</strong>
            </span>
            <input id="shareUrl" type="text" value="{share_url}" readonly
                   onclick="this.select()"
                   style="flex:1;padding:6px 10px;border:1px solid #c5d9ea;
                          border-radius:4px;font-size:13px;background:white;
                          color:#262730;font-family:monospace;" />
            <button id="copyBtn" onclick="
                navigator.clipboard.writeText(document.getElementById('shareUrl').value);
                var b=document.getElementById('copyBtn');
                var t=b.innerText;b.innerText='Copied!';b.style.background='#2e7d32';
                setTimeout(function(){{b.innerText=t;b.style.background='#1c83e1';}}, 1500);
            " style="padding:6px 14px;background:#1c83e1;color:white;border:none;
                    border-radius:4px;cursor:pointer;font-size:13px;font-weight:600;
                    white-space:nowrap;">Copy link</button>
        </div>
        """,
        height=60,
    )

    # Display vehicle info — plate number with device_id as a subtle subtitle
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"""
            <div data-testid="stMetric" style="margin-bottom:8px;">
                <div style="font-size:14px;color:rgba(49,51,63,0.6);font-weight:400;
                            line-height:1.6;">Plate Number</div>
                <div style="font-size:36px;color:rgb(49,51,63);font-weight:400;
                            line-height:1.2;">{vehicle_info['plate_number']}</div>
                <div style="font-size:12px;color:rgba(49,51,63,0.5);font-weight:400;
                            font-family:monospace;margin-top:2px;">
                    {selected_device_id}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col2:
        st.metric("Tracking Since", vehicle_info['time_added'])

    st.markdown("---")

    # Fetch device history from Tenderd API
    with st.spinner("Loading vehicle location history from Tenderd API..."):
        device_history = fetch_device_history(
            selected_device_id,
            vehicle_info['time_added']
        )

    if device_history.empty:
        st.warning(
            "No location history is available for this vehicle right now. "
            "The tracking service may be temporarily unavailable — please try again in a moment."
        )
    else:
        # Create two columns for map and data
        col_map, col_data = st.columns([2, 1])

        with col_map:
            st.subheader("Vehicle Path")
            vehicle_map = create_map(
                device_history,
                selected_device_id,
                vehicle_info['plate_number']
            )
            if vehicle_map:
                folium_static(vehicle_map, width=800, height=600)

        with col_data:
            st.subheader("Statistics")

            # Calculate statistics
            avg_speed = device_history['speed'].mean()
            max_speed = device_history['speed'].max()
            tracking_duration = (
                device_history['timestamp'].max() - device_history['timestamp'].min()
            )
            last_updated = device_history['timestamp'].max()

            st.metric("Average Speed", f"{avg_speed:.1f} km/h")
            st.metric("Max Speed", f"{max_speed:.1f} km/h")
            st.metric(
                "Tracking Duration",
                str(tracking_duration).split('.')[0]
            )

            # Last Updated — smaller font so it doesn't overflow
            st.markdown(
                f"""
                <div style="margin-top:12px;">
                    <div style="font-size:14px;color:rgba(49,51,63,0.6);
                                font-weight:400;line-height:1.6;">Last Updated</div>
                    <div style="font-size:18px;color:rgb(49,51,63);
                                font-weight:600;line-height:1.4;">
                        {last_updated.strftime('%Y-%m-%d %H:%M:%S')} UAE
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.markdown("---")
            st.subheader("Recent Locations")

            # Show last 5 locations, most-recent first, with Google Maps link
            recent_data = device_history.tail(5).iloc[::-1][
                ['timestamp', 'latitude', 'longitude', 'speed']
            ].copy()
            recent_data['location'] = recent_data.apply(
                lambda r: f"https://www.google.com/maps?q={r['latitude']},{r['longitude']}",
                axis=1
            )
            recent_data['speed'] = recent_data['speed'].apply(lambda x: f"{x:.1f} km/h")
            recent_data['timestamp'] = recent_data['timestamp'].dt.strftime('%H:%M:%S')
            recent_data = recent_data[['timestamp', 'location', 'speed']]

            st.dataframe(
                recent_data,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "location": st.column_config.LinkColumn(
                        "Location",
                        display_text="View on Google Maps"
                    )
                }
            )

        # Expandable section — last 24 hours of location history
        with st.expander("View Last 24h Location History"):
            cutoff = device_history['timestamp'].max() - pd.Timedelta(hours=24)
            recent_history = device_history[device_history['timestamp'] >= cutoff]

            st.dataframe(
                recent_history,
                use_container_width=True,
                height=400,
                column_config={
                    "speed": st.column_config.NumberColumn(format="%.1f km/h"),
                    "heading": st.column_config.NumberColumn(format="%.1f°"),
                    "latitude": st.column_config.NumberColumn(format="%.6f"),
                    "longitude": st.column_config.NumberColumn(format="%.6f"),
                }
            )

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>"
    "Vehicle Tracking System | Powered by Streamlit"
    "</div>",
    unsafe_allow_html=True
)
render_logo(width=160, align="center", margin_bottom=4)
