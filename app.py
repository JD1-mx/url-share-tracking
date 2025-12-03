import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta
import random
import numpy as np

# Configure page
st.set_page_config(
    page_title="Vehicle Tracking System",
    page_icon="🚛",
    layout="wide"
)

# Sample Google Sheet data (in production, this would be fetched from the actual sheet)
# Sheet URL: https://docs.google.com/spreadsheets/d/1v6nVIvSm-Lg685aYponZVnopSmQYGdyvpjXpY39fQ3c/edit?usp=sharing
SHARED_VEHICLES = {
    "IFFCO-001": {"plate_number": "DXB-12345", "time_added": "2025-12-03 08:00:00"},
    "IFFCO-002": {"plate_number": "DXB-67890", "time_added": "2025-12-03 09:30:00"},
    "IFFCO-003": {"plate_number": "AD-54321", "time_added": "2025-12-03 10:15:00"},
    "IFFCO-004": {"plate_number": "SHJ-98765", "time_added": "2025-12-03 11:45:00"},
}

def generate_dummy_device_history(device_id, start_time):
    """
    Generate dummy device history data for a vehicle.
    Creates a realistic path with GPS coordinates.
    """
    # Starting point (Dubai area coordinates as example)
    start_lat = 25.2048
    start_lon = 55.2708

    # Parse start time
    if isinstance(start_time, str):
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    else:
        start_dt = start_time

    # Generate path data
    history = []
    current_lat = start_lat
    current_lon = start_lon
    current_time = start_dt

    # Generate 50 points representing movement over time
    num_points = 50
    for i in range(num_points):
        # Simulate realistic vehicle movement
        # Move in a general direction with some variance
        current_lat += random.uniform(-0.005, 0.01)  # Northward bias
        current_lon += random.uniform(-0.005, 0.01)  # Eastward bias
        current_time += timedelta(minutes=random.randint(5, 15))

        # Simulate speed (km/h)
        speed = random.uniform(20, 80)

        history.append({
            "device_id": device_id,
            "timestamp": current_time,
            "latitude": current_lat,
            "longitude": current_lon,
            "speed": speed,
            "heading": random.uniform(0, 360)
        })

    return pd.DataFrame(history)

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

# Sidebar
with st.sidebar:
    st.header("About")
    st.info(
        "This system tracks vehicles that have been shared for monitoring. "
        "Select a vehicle from the dropdown to view its historical path."
    )

    st.markdown("### System Info")
    st.markdown(f"**Total Shared Vehicles:** {len(SHARED_VEHICLES)}")
    st.markdown(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Main content
if not SHARED_VEHICLES:
    st.warning("No vehicles are currently being shared for tracking.")
else:
    # Create dropdown with vehicle info
    vehicle_options = [
        f"{device_id} - {info['plate_number']}"
        for device_id, info in SHARED_VEHICLES.items()
    ]

    selected_option = st.selectbox(
        "Select a vehicle to track:",
        options=vehicle_options,
        index=0
    )

    # Extract device_id from selection
    selected_device_id = selected_option.split(" - ")[0]
    vehicle_info = SHARED_VEHICLES[selected_device_id]

    # Display vehicle info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Device ID", selected_device_id)
    with col2:
        st.metric("Plate Number", vehicle_info['plate_number'])
    with col3:
        st.metric("Tracking Since", vehicle_info['time_added'])

    st.markdown("---")

    # Generate device history
    with st.spinner("Loading vehicle location history..."):
        device_history = generate_dummy_device_history(
            selected_device_id,
            vehicle_info['time_added']
        )

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
