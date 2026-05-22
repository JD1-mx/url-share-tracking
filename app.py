import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta
import requests
import pytz

# Configure page
st.set_page_config(
    page_title="Vehicle Tracking System",
    page_icon="🚛",
    layout="wide"
)

# Webhook URL for fetching shared vehicles
WEBHOOK_URL = "https://tenderd.app.n8n.cloud/webhook/89b4621a-5e8a-4a4b-a2ed-40f1aaf2e2cf"

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

    # Get center point (average of all coordinates)
    center_lat = device_history_df['latitude'].mean()
    center_lon = device_history_df['longitude'].mean()

    # Create map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=12,
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

    # Add start marker (green)
    folium.Marker(
        [device_history_df.iloc[0]['latitude'], device_history_df.iloc[0]['longitude']],
        popup=f"Start: {device_history_df.iloc[0]['timestamp']}",
        icon=folium.Icon(color='green', icon='play')
    ).add_to(m)

    # Add end marker (red)
    folium.Marker(
        [device_history_df.iloc[-1]['latitude'], device_history_df.iloc[-1]['longitude']],
        popup=f"Latest: {device_history_df.iloc[-1]['timestamp']}",
        icon=folium.Icon(color='red', icon='stop')
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

    return m

# Main app
st.title("🚛 Vehicle Tracking System")
st.markdown("---")

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

# Main content
if not SHARED_VEHICLES:
    st.warning("No vehicles are currently being shared for tracking.")
else:
    # Create dropdown with vehicle info
    vehicle_options = [
        f"{device_id} - {info['plate_number']}"
        for device_id, info in SHARED_VEHICLES.items()
    ]

    # Check for device_id in query parameters
    query_params = st.query_params
    url_device_id = query_params.get("device_id", None)

    # Determine initial index based on URL parameter
    initial_index = 0
    if url_device_id and url_device_id in SHARED_VEHICLES:
        # Find the index of the device in the options list
        for idx, option in enumerate(vehicle_options):
            if option.startswith(url_device_id):
                initial_index = idx
                break

    selected_option = st.selectbox(
        "Select a vehicle to track:",
        options=vehicle_options,
        index=initial_index
    )

    # Extract device_id from selection
    selected_device_id = selected_option.split(" - ")[0]
    vehicle_info = SHARED_VEHICLES[selected_device_id]

    # Update URL query parameter when selection changes
    if query_params.get("device_id") != selected_device_id:
        st.query_params["device_id"] = selected_device_id

    # Display shareable link
    st.info(f"📋 **Share this vehicle:** `?device_id={selected_device_id}`")

    # Display vehicle info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Device ID", selected_device_id)
    with col2:
        st.metric("Plate Number", vehicle_info['plate_number'])
    with col3:
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
            total_points = len(device_history)
            avg_speed = device_history['speed'].mean()
            max_speed = device_history['speed'].max()
            time_span = (device_history['timestamp'].max() - device_history['timestamp'].min())

            st.metric("Total Data Points", total_points)
            st.metric("Average Speed", f"{avg_speed:.1f} km/h")
            st.metric("Max Speed", f"{max_speed:.1f} km/h")
            st.metric("Time Span", str(time_span).split('.')[0])

            st.markdown("---")
            st.subheader("Recent Locations")

            # Show last 5 locations
            recent_data = device_history.tail(5)[['timestamp', 'latitude', 'longitude', 'speed']].copy()
            recent_data['speed'] = recent_data['speed'].apply(lambda x: f"{x:.1f} km/h")
            recent_data['timestamp'] = recent_data['timestamp'].dt.strftime('%H:%M:%S')

            st.dataframe(
                recent_data,
                hide_index=True,
                use_container_width=True
            )

        # Expandable section for full data
        with st.expander("View Full Location History"):
            st.dataframe(
                device_history.style.format({
                    'speed': '{:.1f} km/h',
                    'heading': '{:.1f}°',
                    'latitude': '{:.6f}',
                    'longitude': '{:.6f}'
                }),
                use_container_width=True,
                height=400
            )

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>"
    "Vehicle Tracking System | Powered by Streamlit"
    "</div>",
    unsafe_allow_html=True
)
