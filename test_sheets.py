import os
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SPREADSHEET_ID = "1baRT4upMcOCyZjVSNsw0RLiT5A5z1MDfsTPYfyg35xo"
CREDENTIALS_FILE = "credentials.json"
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.readonly'
]

def test_connection():
    # Make sure we check env var first just like the app does
    service_account_info = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    spreadsheet_id = os.environ.get("GOOGLE_SPREADSHEET_ID", SPREADSHEET_ID)

    try:
        if service_account_info:
            print("Authenticating with GOOGLE_SERVICE_ACCOUNT_JSON env variable...")
            info = json.loads(service_account_info)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        else:
            print(f"Authenticating with local file '{CREDENTIALS_FILE}'...")
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"ERROR: {CREDENTIALS_FILE} not found. Please place your service account JSON file in the project root.")
                return
            creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        
        service = build('sheets', 'v4', credentials=creds).spreadsheets()
        print("Contacting Google Sheets API...")
        
        # Read the spreadsheet metadata
        sheet_metadata = service.get(spreadsheetId=spreadsheet_id).execute()
        print("\n🎉 SUCCESS! Google Sheets API connection is working correctly.")
        print(f"Spreadsheet Title: {sheet_metadata.get('properties', {}).get('title')}")
        print("Accessible Tabs:")
        for s in sheet_metadata.get('sheets', []):
            print(f" - {s.get('properties', {}).get('title')}")
            
    except Exception as e:
        print("\n❌ CONNECTION FAILED!")
        print(f"Error Details: {e}")
        if "invalid_grant" in str(e):
            print("\n💡 What 'invalid_grant' means:")
            print("This means Google rejected your credentials token signature. Common reasons:")
            print("1. The service account credentials inside your JSON file have been deleted or disabled in GCP.")
            print("2. The private key in the JSON key file is revoked or was modified/corrupted.")
            print("3. Your local system time is out of sync with Google's servers (check your system clock).")

if __name__ == '__main__':
    test_connection()
