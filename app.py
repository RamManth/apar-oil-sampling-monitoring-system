import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

app = Flask(__name__)
app.secret_key = os.urandom(24)

# 🔴 CONFIGURATION: Replace with the single ID from your Google Sheet URL
SPREADSHEET_ID = "1baRT4upMcOCyZjVSNsw0RLiT5A5z1MDfsTPYfyg35xo"

CREDENTIALS_FILE = "credentials.json"
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.readonly'
]

def get_sheets_service():
    """Authenticates using credentials.json and builds the Google Sheets connection."""
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError("Missing credentials.json file in project root folder.")
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds).spreadsheets()

def check_upcoming_alarms():
    """Scans the live Google Sheet matrix for pending deadlines inside the warning window."""
    alarms = []
    try:
        service = get_sheets_service()
        result = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Evaluation Data Rowwise!A6:O").execute()
        rows = result.get('values', [])

        today_dt = datetime.now()
        valid_alarm_dates = [
            today_dt.strftime("%d-%m-%Y"),                          
            (today_dt + timedelta(days=1)).strftime("%d-%m-%Y"),     
            (today_dt + timedelta(days=2)).strftime("%d-%m-%Y")      
        ]

        for idx, row in enumerate(rows):
            while len(row) < 15:
                row.append("")

            status_val = row[14] # Column O (Index 14)
            if status_val and status_val.strip().lower() == "done":
                continue

            deadline_val = row[13] # Column N (Index 13)
            if not deadline_val:
                continue

            clean_deadline = str(deadline_val).strip().split()[0]
            try:
                if "-" in clean_deadline and clean_deadline.index("-") == 4:
                    clean_deadline = datetime.strptime(clean_deadline, "%Y-%m-%d").strftime("%d-%m-%Y")
            except Exception:
                pass

            if clean_deadline in valid_alarm_dates:
                if clean_deadline == valid_alarm_dates[0]:
                    status = "CRITICAL: DUE TODAY"
                elif clean_deadline == valid_alarm_dates[1]:
                    status = "URGENT: 1 Day Remaining"
                else:
                    status = "WARNING: 2 Days Remaining"

                alarms.append({
                    "id": row[0],  
                    "executive": row[1] if len(row) > 1 else "Unknown",
                    "customer": row[3] if len(row) > 3 else "Unknown",
                    "deadline": clean_deadline,
                    "status": status,
                    "sheet_row_index": idx + 6 
                })
    except Exception as e:
        print(f"⚠️ Cloud Alarm Engine warning: {e}")
    return alarms

def get_handlers_status():
    """Compiles handler options list, pulling dynamically from the Handlers Directory tab."""
    handlers = []
    try:
        service = get_sheets_service()
        # Step 1: Fetch handlers from the 'Handlers Directory' tab
        h_result = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Handlers Directory!A2:A").execute()
        h_rows = h_result.get('values', [])
        
        for r in h_rows:
            if r:
                handlers.append({"name": str(r[0]).strip(), "disabled": False})

        # Step 2: Correlate active main sheet tracking allocations to check for duplicates/pendings
        m_result = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Evaluation Data Rowwise!A6:O").execute()
        m_rows = m_result.get('values', [])
        
        for row in m_rows:
            while len(row) < 15:
                row.append("")
            allocated_handler = row[2] # Column C
            status_val = row[14]       # Column O
            
            if allocated_handler and status_val and status_val.strip().lower() == "pending":
                for h in handlers:
                    if h["name"].lower() == str(allocated_handler).strip().lower():
                        h["disabled"] = True
    except Exception as e:
        print(f"⚠️ Handlers dynamic update error: {e}")
        return []
    return handlers

def calculate_deadline(issue_date_str, issue_type):
    try:
        base_date = datetime.strptime(issue_date_str, "%Y-%m-%d")
    except ValueError:
        base_date = datetime.now()
    days_mapping = {"Condition Monitoring": 7, "Complain Handling": 3, "Product Benchmarking": 10}
    return (base_date + timedelta(days=days_mapping.get(issue_type, 0))).strftime("%d-%m-%Y")

@app.route('/', methods=['GET', 'POST'])
def evaluation_form():
    service = get_sheets_service()

    if request.method == 'POST':
        form_data = {
            "executive_name": request.form.get("executive_name", "").strip(),
            "handler_name": request.form.get("handler_name", "").strip(),
            "customer_details": request.form.get("customer_details", "").strip(),
            "issue_type": request.form.get("issue_type", "").strip(),
            "issue_date": request.form.get("issue_date", "").strip(),
            "product_name": request.form.get("product_name", "").strip(),
            "machine_collected": request.form.get("machine_collected", "").strip(),
            "point_of_collection": request.form.get("point_of_collection", "").strip(),
            "quantity_sent": request.form.get("quantity_sent", "").strip(),
            "competitor_info": request.form.get("competitor_info", "").strip(),
            "application_details": request.form.get("application_details", "").strip(),
            "test_parameters": request.form.get("test_parameters", "").strip()
        }

        deadline_date = calculate_deadline(form_data["issue_date"], form_data["issue_type"])
        try:
            formatted_issue_date = datetime.strptime(form_data["issue_date"], "%Y-%m-%d").strftime("%d-%m-%Y")
        except ValueError:
            formatted_issue_date = form_data["issue_date"]

        try:
            current_data = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Evaluation Data Rowwise!A6:A").execute()
            next_id = len(current_data.get('values', [])) + 1
        except Exception:
            next_id = 1

        new_row = [
            next_id, form_data["executive_name"], form_data["handler_name"], form_data["customer_details"], form_data["issue_type"],
            formatted_issue_date, form_data["product_name"], form_data["machine_collected"],
            form_data["point_of_collection"], form_data["quantity_sent"], form_data["competitor_info"],
            form_data["application_details"], form_data["test_parameters"], deadline_date, "Pending"
        ]

        body = {'values': [new_row]}
        service.values().append(
            spreadsheetId=SPREADSHEET_ID, 
            range="Evaluation Data Rowwise!A6", 
            valueInputOption="RAW", 
            body=body
        ).execute()

        flash("Submission synced directly to Google Sheets!", "success")
        return redirect(url_for('evaluation_form'))

    active_alarms = check_upcoming_alarms()
    handlers_list = get_handlers_status()
    return render_template('form.html', active_alarms=active_alarms, handlers_list=handlers_list)

@app.route('/mark_done/<int:record_id>', methods=['POST'])
def mark_done(record_id):
    try:
        service = get_sheets_service()
        result = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Evaluation Data Rowwise!A6:A").execute()
        ids = result.get('values', [])
        
        row_target = None
        for idx, row_id_list in enumerate(ids):
            if row_id_list and int(row_id_list[0]) == record_id:
                row_target = idx + 6 
                break

        if row_target:
            body = {'values': [["Done"]]}
            service.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"Evaluation Data Rowwise!O{row_target}",
                valueInputOption="RAW",
                body=body
            ).execute()
            flash(f"Task ID #{record_id} successfully updated to 'Done' on Google Sheets!", "success")
    except Exception as e:
        flash(f"Cloud update error: {e}", "danger")
    return redirect(url_for('evaluation_form'))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=True)