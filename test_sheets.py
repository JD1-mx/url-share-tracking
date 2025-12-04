#!/usr/bin/env python3
"""
Quick test script to verify webhook connection
Run this before starting the Streamlit app to verify the webhook is accessible
"""

import requests
import json

WEBHOOK_URL = "https://tenderd.app.n8n.cloud/webhook/89b4621a-5e8a-4a4b-a2ed-40f1aaf2e2cf"

def test_webhook():
    print("Testing webhook connection...")
    print(f"Webhook URL: {WEBHOOK_URL}\n")

    try:
        print("Attempting to fetch data from webhook...")
        response = requests.get(WEBHOOK_URL, timeout=10)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            print("✓ Connection successful!\n")

            # Parse JSON response
            try:
                data = response.json()
                print(f"Response type: {type(data)}")

                if isinstance(data, list):
                    print(f"Total records: {len(data)}\n")

                    if len(data) > 0:
                        print("Sample record:")
                        print(json.dumps(data[0], indent=2))

                        # Check for required fields
                        required_fields = ['device_id', 'plate_number', 'time_added']
                        missing_fields = [field for field in required_fields if field not in data[0]]

                        if missing_fields:
                            print(f"\n⚠️  WARNING: Missing required fields: {', '.join(missing_fields)}")
                        else:
                            print("\n✓ All required fields present!")

                        print("\nAll records:")
                        for i, record in enumerate(data, 1):
                            device_id = record.get('device_id', 'N/A')
                            plate_number = record.get('plate_number', 'N/A')
                            time_added = record.get('time_added', 'N/A')
                            print(f"{i}. {device_id} - {plate_number} (Added: {time_added})")

                        return True
                    else:
                        print("⚠️  Webhook returned empty list")
                        return False
                else:
                    print(f"⚠️  Expected list, got: {type(data)}")
                    print(f"Response: {json.dumps(data, indent=2)}")
                    return False

            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse JSON response: {str(e)}")
                print(f"Raw response: {response.text[:500]}")
                return False

        else:
            print(f"❌ Request failed with status code: {response.status_code}")
            print(f"Response: {response.text[:500]}")

            print("\n\nTroubleshooting steps:")
            print("1. Make sure the n8n workflow is ACTIVE (toggle in top-right of editor)")
            print("2. Verify the webhook URL is correct")
            print("3. Check that the webhook is configured for GET requests")
            print("4. Test the webhook in n8n using 'Test workflow' button")
            print(f"5. Try opening this URL in your browser:")
            print(f"   {WEBHOOK_URL}")

            return False

    except requests.RequestException as e:
        print(f"❌ Network error: {str(e)}")
        print("\n\nTroubleshooting steps:")
        print("1. Check your internet connection")
        print("2. Verify the webhook URL is accessible")
        print(f"3. Try opening this URL in your browser:")
        print(f"   {WEBHOOK_URL}")
        return False

if __name__ == "__main__":
    success = test_webhook()
    exit(0 if success else 1)
