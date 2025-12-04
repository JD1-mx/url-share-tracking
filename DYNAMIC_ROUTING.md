# Dynamic Routing Feature

The Vehicle Tracking System now supports direct links to specific vehicles using query parameters.

## How to Use

### Method 1: Query Parameter (Recommended)

Add `?device_id=<DEVICE_ID>` to the URL:

```
http://localhost:8501/?device_id=ds5xDNtfTGrkdKebivub
```

This will automatically select the specified device when the page loads.

### Method 2: Copy Share Link

1. Open the app at http://localhost:8501
2. Select a vehicle from the dropdown
3. Look for the blue info box that shows: `📋 Share this vehicle: ?device_id=...`
4. Copy the query parameter and append it to your base URL
5. Share the complete URL with others

## Examples

### Example 1: Direct Link to Device
```
http://localhost:8501/?device_id=ds5xDNtfTGrkdKebivub
```
Opens the app with device `ds5xDNtfTGrkdKebivub` already selected.

### Example 2: Production URL
```
https://your-domain.com/?device_id=IFFCO-001
```
Works with any deployment URL, just replace the base URL.

## How It Works

1. **URL Detection**: When you open a URL with `?device_id=<DEVICE_ID>`, the app reads this parameter
2. **Auto-Selection**: If the device exists in the webhook data, it's automatically selected in the dropdown
3. **URL Updates**: When you manually select a different vehicle, the URL automatically updates with the new device_id
4. **Sharing**: The current selection is always reflected in the URL, making it easy to share specific vehicle views

## Technical Details

- Uses Streamlit's `st.query_params` for URL parameter management
- Automatically validates that the device_id exists before selection
- Falls back to first device if invalid device_id is provided
- URL updates happen automatically without page reload

## Benefits

- **Direct Access**: Skip the dropdown and go straight to a specific vehicle
- **Bookmarkable**: Save specific vehicle views as bookmarks
- **Shareable**: Send exact links to colleagues
- **Integration-Friendly**: Easy to integrate with other systems that need to link to specific vehicles
