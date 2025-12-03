# Vehicle Tracking System - Streamlit Demo

A Streamlit application that demonstrates vehicle tracking and visualization based on shared vehicle data from Google Sheets.

## Features

- **Vehicle Selection**: Dropdown menu to select from available shared vehicles (from IFFCO fleet)
- **Interactive Map**: Visualize the complete path of a vehicle from the time it was added
- **Real-time Statistics**: View metrics like average speed, max speed, and time span
- **Location History**: Browse detailed location history with timestamps and coordinates
- **Path Visualization**:
  - Green marker for starting point
  - Red marker for latest location
  - Blue line showing the complete path
  - Intermediate markers showing progression

## Installation

1. Make sure you have Python 3.8+ installed

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

```bash
streamlit run app.py
```

The application will open in your default web browser at `http://localhost:8501`

## How It Works

### Current Implementation (Demo)

The current version uses dummy data to demonstrate the concept:

- **Shared Vehicles**: Hardcoded sample data representing the vehicles tracked in the Google Sheet
- **Device History**: Randomly generated but realistic GPS coordinates simulating vehicle movement
- **4 Sample Vehicles**: IFFCO-001 through IFFCO-004 with plate numbers and tracking start times

### Production Integration

To integrate with real data, you would need to:

1. **Google Sheets Integration**:
   - Use `gspread` or Google Sheets API to fetch vehicle data
   - Read from: https://docs.google.com/spreadsheets/d/1v6nVIvSm-Lg685aYponZVnopSmQYGdyvpjXpY39fQ3c/edit?usp=sharing
   - Columns: `device_id`, `plate_number`, `time_added`

2. **Database Integration**:
   - Connect to your `device_histories` collection
   - Query historical location documents for selected vehicles
   - Filter data from `time_added` onwards

3. **n8n Workflow**:
   - Form to add vehicle ID to sheet (start sharing)
   - Form to remove vehicle ID from sheet (stop sharing)
   - Generate/revoke share links

## Data Structure

### Shared Vehicles (from Google Sheet)
```
device_id    | plate_number | time_added
-------------|--------------|-------------------
IFFCO-001    | DXB-12345    | 2025-12-03 08:00:00
```

### Device History (from device_histories collection)
```
device_id    | timestamp           | latitude  | longitude | speed | heading
-------------|---------------------|-----------|-----------|-------|--------
IFFCO-001    | 2025-12-03 08:05:00 | 25.2048   | 55.2708   | 45.5  | 180.0
```

## Project Structure

```
url share tracking/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
├── README.md          # This file
└── request.md         # Original requirements
```

## Customization

### Adding Real Google Sheets Integration

Install additional dependencies:
```bash
pip install gspread oauth2client
```

Replace the `SHARED_VEHICLES` dictionary in `app.py:19` with:
```python
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_shared_vehicles():
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_url('YOUR_SHEET_URL').sheet1
    records = sheet.get_all_records()

    return {
        row['device_id']: {
            'plate_number': row['plate_number'],
            'time_added': row['time_added']
        }
        for row in records
    }
```

### Connecting to Database

Replace the `generate_dummy_device_history()` function with your actual database query:
```python
def get_device_history(device_id, start_time):
    # Connect to your database (MongoDB, PostgreSQL, etc.)
    # Query device_histories collection
    # Filter by device_id and timestamp >= start_time
    # Return as pandas DataFrame
    pass
```

## Technologies Used

- **Streamlit**: Web application framework
- **Folium**: Interactive map visualization
- **Pandas**: Data manipulation
- **NumPy**: Numerical operations

## Future Enhancements

- Real-time updates using websockets
- Date range filtering for historical data
- Multiple vehicle comparison view
- Export tracking data to CSV/Excel
- Share link generation for specific vehicles
- Authentication and access control
