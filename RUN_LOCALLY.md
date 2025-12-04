# Running the Vehicle Tracking System Locally

## Setup Instructions

### 1. Create a virtual environment
```bash
python3 -m venv venv
```

### 2. Activate the virtual environment
```bash
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up secrets (API Key)
```bash
# Copy the secrets template
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# Edit the file and add your actual API key
# See SECRETS_SETUP.md for detailed instructions
```

### 5. (Optional) Test the webhook connection
```bash
python test_sheets.py
```

### 6. Run the Streamlit app
```bash
streamlit run app.py
```

### 7. Access the app
The app will automatically open in your browser at `http://localhost:8501`

If it doesn't open automatically, you can manually navigate to that URL.

#### Direct Links to Specific Vehicles
You can link directly to a specific vehicle using query parameters:
```
http://localhost:8501/?device_id=ds5xDNtfTGrkdKebivub
```

See [DYNAMIC_ROUTING.md](DYNAMIC_ROUTING.md) for more details on this feature.

## Deactivating the virtual environment
When you're done testing, deactivate the virtual environment:
```bash
deactivate
```

## Troubleshooting

### Webhook Access Issues
If you see errors about accessing the webhook:
1. Make sure the n8n workflow is **ACTIVE** (toggle in top-right of the editor)
2. Verify the webhook URL is correct in `app.py`
3. Check that the webhook is configured for **GET** requests
4. Test the webhook using the test script: `python test_sheets.py`
5. Click the "Refresh Data" button in the sidebar of the app

### Expected Webhook Response Format
The webhook should return a JSON array with objects containing these fields:
- `device_id` - Vehicle device identifier (e.g., "ds5xDNtfTGrkdKebivub")
- `plate_number` - License plate number (e.g., "DXB /10808")
- `time_added` - Timestamp when tracking started (e.g., "2025-12-03 8:00:00")

Example response:
```json
[
    {
        "row_number": 2,
        "device_id": "ds5xDNtfTGrkdKebivub",
        "plate_number": "DXB /10808",
        "time_added": "2025-12-03 8:00:00",
        "myNewField": 1
    },
    {
        "row_number": 3,
        "device_id": "IFFCO-002",
        "plate_number": "DXB-67890",
        "time_added": "2025-12-03 9:30:00",
        "myNewField": 1
    }
]
```

**Note:** Additional fields like `row_number` and `myNewField` are ignored by the app.
