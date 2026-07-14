import os
import json
import smtplib
import threading
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pytz
from flask import Flask, render_template, request, redirect, url_for, flash, session
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

class SheetsCache:
    def __init__(self, ttl_seconds=10):
        self.ttl = ttl_seconds
        self.data = {}
        self.last_fetched = {}
        self.lock = threading.Lock()
        
    def get(self, key):
        with self.lock:
            if key in self.data:
                if time.time() - self.last_fetched[key] < self.ttl:
                    return self.data[key]
            return None
            
    def set(self, key, value):
        with self.lock:
            self.data[key] = value
            self.last_fetched[key] = time.time()
            
    def clear(self):
        with self.lock:
            self.data.clear()
            self.last_fetched.clear()

sheets_cache = SheetsCache(ttl_seconds=10)


# Helper function to load environment variables from .env / .env.local without external packages
def load_env_file(filepath=".env"):
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    os.environ[key] = val

load_env_file(".env")
load_env_file(".env.local")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "apar_default_secret_key_for_dev_only")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "apar2026")

# 🔴 CONFIGURATION: Replace with the single ID from your Google Sheet URL
SPREADSHEET_ID = os.environ.get("GOOGLE_SPREADSHEET_ID", "1baRT4upMcOCyZjVSNsw0RLiT5A5z1MDfsTPYfyg35xo")

CREDENTIALS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.readonly'
]

# SMTP Configuration
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").replace(" ", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", SMTP_USERNAME)

SENT_LOG_FILE = os.path.join(BASE_DIR, "sent_emails_log.json")

def get_sent_emails():
    try:
        if os.path.exists(SENT_LOG_FILE):
            with open(SENT_LOG_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_sent_email(log_key, today_str):
    emails = get_sent_emails()
    emails[log_key] = today_str
    try:
        with open(SENT_LOG_FILE, "w") as f:
            json.dump(emails, f)
    except Exception as e:
        print(f"Error saving sent email log: {e}")

def get_sheets_service():
    """Authenticates using environment variable or credentials.json and builds the Google Sheets connection."""
    service_account_info = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if service_account_info:
        try:
            info = json.loads(service_account_info)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception as e:
            raise ValueError(f"Failed to load credentials from GOOGLE_SERVICE_ACCOUNT_JSON: {e}")
    else:
        if not os.path.exists(CREDENTIALS_FILE):
            raise FileNotFoundError("Missing credentials.json file in project root folder or GOOGLE_SERVICE_ACCOUNT_JSON env variable.")
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds).spreadsheets()

def get_handler_email_map():
    """Fetches the handler email map from the Handlers Directory."""
    email_map = {}
    try:
        cached_rows = sheets_cache.get("handlers_directory")
        if cached_rows is not None:
            h_rows = cached_rows
        else:
            service = get_sheets_service()
            h_result = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Handlers Directory!A2:B").execute()
            h_rows = h_result.get('values', [])
            sheets_cache.set("handlers_directory", h_rows)
        for r in h_rows:
            if r and len(r) > 0 and str(r[0]).strip():
                name = str(r[0]).strip().lower()
                email = str(r[1]).strip() if len(r) > 1 and str(r[1]).strip() else f"{name.replace(' ', '')}@example.com"
                email_map[name] = email
    except Exception as e:
        print(f"⚠️ Error loading handler email map: {e}")
    return email_map

def send_handler_email(handler_email, handler_name, job_details, status):
    """Sends an email warning the handler that their job is close to due."""
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print("⚠️ SMTP credentials not set. Skipping email dispatch.")
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"🚨 URGENT: Job #{job_details['id']} is {status}!"
        msg['From'] = SENDER_EMAIL
        msg['To'] = handler_email

        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; color: #1e293b; background-color: #f8fafc; margin: 0; padding: 20px; }}
                .container {{ max-width: 600px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
                .header {{ background-color: #111827; color: #ffffff; padding: 20px; text-align: center; }}
                .header h2 {{ margin: 0; font-size: 1.4rem; letter-spacing: 0.5px; text-transform: uppercase; }}
                .body {{ padding: 24px; }}
                .alert {{ background-color: #fef2f2; border-left: 4px solid #ef4444; color: #991b1b; padding: 12px 16px; border-radius: 6px; margin-bottom: 20px; font-weight: 600; }}
                .table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                .table th {{ background-color: #f1f5f9; text-align: left; padding: 8px 12px; font-size: 0.8rem; text-transform: uppercase; color: #64748b; border-bottom: 1px solid #e2e8f0; }}
                .table td {{ padding: 10px 12px; font-size: 0.9rem; border-bottom: 1px solid #e2e8f0; color: #334155; }}
                .footer {{ background-color: #f8fafc; padding: 15px; text-align: center; font-size: 0.8rem; color: #64748b; border-top: 1px solid #e2e8f0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>APAR Oil Sample Monitoring System</h2>
                </div>
                <div class="body">
                    <p>Dear <strong>{handler_name}</strong>,</p>
                    <div class="alert">
                        ⚠️ Alert: The job assigned to you is close to its target deadline. Please clear it before the due date.
                    </div>
                    <h3>Job Details</h3>
                    <table class="table">
                        <tr><th>Job ID</th><td>#{job_details['id']}</td></tr>
                        <tr><th>Executive</th><td>{job_details['executive_name']}</td></tr>
                        <tr><th>Customer Details</th><td>{job_details['customer_details']}</td></tr>
                        <tr><th>Issue Type</th><td>{job_details['issue_type']}</td></tr>
                        <tr><th>Issue Date</th><td>{job_details['issue_date']}</td></tr>
                        <tr><th>Product Full Name</th><td>{job_details['product_name']}</td></tr>
                        <tr><th>Target Deadline</th><td><strong style="color: #ef4444;">{job_details['deadline']}</strong></td></tr>
                        <tr><th>Urgency Status</th><td><strong>{status}</strong></td></tr>
                    </table>
                    <p style="margin-top: 25px; font-size: 0.85rem; color: #64748b;">
                        Please log in to the dashboard to update the job status once resolved.
                    </p>
                </div>
                <div class="footer">
                    APAR Industries &copy; 2026. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_content, 'html'))

        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        else:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
        
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SENDER_EMAIL, handler_email, msg.as_string())
        server.quit()
        print(f"📧 Notification email successfully sent to {handler_email} for Job #{job_details['id']}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email to {handler_email}: {e}")
        return False

def trigger_auto_email_async(handler_email, handler_name, job_details, status):
    thread = threading.Thread(target=send_handler_email, args=(handler_email, handler_name, job_details, status))
    thread.daemon = True
    thread.start()

def check_upcoming_alarms():
    """Scans the live Google Sheet matrix for pending deadlines inside the warning window."""
    alarms = []
    try:
        cached_rows = sheets_cache.get("evaluation_data_rows")
        if cached_rows is not None:
            rows = cached_rows
        else:
            service = get_sheets_service()
            result = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Evaluation Data Rowwise!A6:P").execute()
            rows = result.get('values', [])
            sheets_cache.set("evaluation_data_rows", rows)

        ist = pytz.timezone("Asia/Kolkata")
        today_dt = datetime.now(ist)
        valid_alarm_dates = [
            today_dt.strftime("%d-%m-%Y"),                          
            (today_dt + timedelta(days=1)).strftime("%d-%m-%Y"),     
            (today_dt + timedelta(days=2)).strftime("%d-%m-%Y")      
        ]

        email_map = get_handler_email_map()

        for idx, row in enumerate(rows):
            while len(row) < 16:
                row.append("")

            status_val = row[15] # Column P (Index 15)
            if status_val and status_val.strip().lower() == "done":
                continue

            deadline_val = row[14] # Column O (Index 14)
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

                executive = row[1] if len(row) > 1 else "Unknown"
                customer = row[4] if len(row) > 4 else "Unknown"
                handler_name = row[2].strip() if len(row) > 2 else ""
                handler_email = row[3].strip() if len(row) > 3 else ""

                # Resilient Lookup: Resolve handler email from directory mapping if empty
                if not handler_email and handler_name:
                    handler_email = email_map.get(handler_name.lower(), f"{handler_name.lower().replace(' ', '')}@example.com")

                alarms.append({
                    "id": row[0],  
                    "executive": executive,
                    "customer": customer,
                    "deadline": clean_deadline,
                    "status": status,
                    "sheet_row_index": idx + 6 
                })

                # Process automatic email alert
                if handler_email:
                    job_details = {
                        "id": row[0].strip(),
                        "executive_name": executive,
                        "customer_details": customer,
                        "issue_type": row[5].strip() if len(row) > 5 else "",
                        "issue_date": row[6].strip() if len(row) > 6 else "",
                        "product_name": row[7].strip() if len(row) > 7 else "",
                        "deadline": clean_deadline,
                        "status": status_val.strip() if status_val.strip() else "Pending"
                    }
                    sent_log = get_sent_emails()
                    today_str = today_dt.strftime("%Y-%m-%d")
                    log_key = f"{job_details['id']}_{status}"
                    if log_key not in sent_log or sent_log[log_key] != today_str:
                        trigger_auto_email_async(handler_email, handler_name, job_details, status)
                        save_sent_email(log_key, today_str)

    except Exception as e:
        print(f"⚠️ Cloud Alarm Engine warning: {e}")
    return alarms

def get_handlers_status():
    """Compiles handler options list, pulling dynamically from the Handlers Directory tab."""
    handlers = []
    try:
        cached_h_rows = sheets_cache.get("handlers_directory")
        if cached_h_rows is not None:
            h_rows = cached_h_rows
        else:
            service = get_sheets_service()
            h_result = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Handlers Directory!A2:B").execute()
            h_rows = h_result.get('values', [])
            sheets_cache.set("handlers_directory", h_rows)
        
        for r in h_rows:
            if r and len(r) > 0 and str(r[0]).strip():
                name = str(r[0]).strip()
                email = str(r[1]).strip() if len(r) > 1 and str(r[1]).strip() else f"{name.lower().replace(' ', '')}@example.com"
                handlers.append({"name": name, "email": email, "disabled": False})

        cached_m_rows = sheets_cache.get("evaluation_data_rows")
        if cached_m_rows is not None:
            m_rows = cached_m_rows
        else:
            service = get_sheets_service()
            m_result = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Evaluation Data Rowwise!A6:P").execute()
            m_rows = m_result.get('values', [])
            sheets_cache.set("evaluation_data_rows", m_rows)
        
        for row in m_rows:
            while len(row) < 16:
                row.append("")
            allocated_handler = row[2] # Column C (Index 2)
            status_val = row[15]       # Column P (Index 15)
            
            if allocated_handler and status_val and status_val.strip().lower() == "pending":
                for h in handlers:
                    if h["name"].lower() == str(allocated_handler).strip().lower():
                        h["disabled"] = True
    except Exception as e:
        print(f"⚠️ Handlers dynamic update error: {e}")
        return []
    return handlers

def get_all_jobs():
    """Fetches all evaluation jobs from the Google Sheet (A6:P)."""
    jobs = []
    try:
        cached_rows = sheets_cache.get("evaluation_data_rows")
        if cached_rows is not None:
            rows = cached_rows
        else:
            service = get_sheets_service()
            result = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Evaluation Data Rowwise!A6:P").execute()
            rows = result.get('values', [])
            sheets_cache.set("evaluation_data_rows", rows)
        email_map = get_handler_email_map()

        for idx, row in enumerate(rows):
            while len(row) < 16:
                row.append("")
            
            # Skip empty or header-like rows
            if not row[0] or not str(row[0]).strip():
                continue
                
            handler_name = row[2].strip() if len(row) > 2 else ""
            handler_email = row[3].strip() if len(row) > 3 else ""

            # Resilient Lookup: Resolve handler email from directory mapping if empty
            if not handler_email and handler_name:
                handler_email = email_map.get(handler_name.lower(), f"{handler_name.lower().replace(' ', '')}@example.com")

            jobs.append({
                "id": row[0].strip(),
                "executive_name": row[1].strip() if len(row) > 1 else "",
                "handler_email": handler_email,
                "handler_name": handler_name,
                "customer_details": row[4].strip() if len(row) > 4 else "",
                "issue_type": row[5].strip() if len(row) > 5 else "",
                "issue_date": row[6].strip() if len(row) > 6 else "",
                "product_name": row[7].strip() if len(row) > 7 else "",
                "deadline": row[14].strip() if len(row) > 14 else "",
                "status": row[15].strip() if len(row) > 15 and row[15].strip() else "Pending",
                "sheet_row_index": idx + 6
            })
    except Exception as e:
        print(f"⚠️ Error fetching all jobs: {e}")
    return jobs

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
            "handler_email": request.form.get("handler_email", "").strip(),
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
            values = current_data.get('values', [])
            numeric_ids = []
            for v in values:
                if v and str(v[0]).isdigit():
                    numeric_ids.append(int(v[0]))
            next_id = max(numeric_ids) + 1 if numeric_ids else 1
        except Exception as e:
            print(f"⚠️ Error fetching IDs, fallback to sequential increment: {e}")
            next_id = 1

        new_row = [
            next_id, form_data["executive_name"], form_data["handler_name"], form_data["handler_email"], form_data["customer_details"],
            form_data["issue_type"], formatted_issue_date, form_data["product_name"], form_data["machine_collected"],
            form_data["point_of_collection"], form_data["quantity_sent"], form_data["competitor_info"],
            form_data["application_details"], form_data["test_parameters"], deadline_date, "Pending"
        ]

        try:
            body = {'values': [new_row]}
            service.values().append(
                spreadsheetId=SPREADSHEET_ID, 
                range="Evaluation Data Rowwise!A6", 
                valueInputOption="RAW", 
                body=body
            ).execute()
            sheets_cache.clear()  # Clear cache on new write
            flash("Submission synced directly to Google Sheets!", "success")
        except Exception as e:
            flash(f"Sync failed! Failed to write to Google Sheets: {e}", "danger")
        return redirect(url_for('evaluation_form'))

    active_alarms = check_upcoming_alarms()
    handlers_list = get_handlers_status()
    all_jobs = get_all_jobs()
    return render_template('form.html', active_alarms=active_alarms, handlers_list=handlers_list, all_jobs=all_jobs)

@app.route('/mark_done/<int:record_id>', methods=['POST'])
def mark_done(record_id):
    try:
        service = get_sheets_service()
        result = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Evaluation Data Rowwise!A6:A").execute()
        ids = result.get('values', [])
        
        row_target = None
        for idx, row_id_list in enumerate(ids):
            if row_id_list and str(row_id_list[0]).isdigit() and int(row_id_list[0]) == record_id:
                row_target = idx + 6 
                break

        if row_target:
            body = {'values': [["Done"]]}
            service.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"Evaluation Data Rowwise!P{row_target}",
                valueInputOption="RAW",
                body=body
            ).execute()
            sheets_cache.clear()  # Clear cache on write
            flash(f"Task ID #{record_id} successfully updated to 'Done' on Google Sheets!", "success")
    except Exception as e:
        flash(f"Cloud update error: {e}", "danger")
    return redirect(url_for('evaluation_form'))

@app.route('/update_status/<int:record_id>', methods=['POST'])
def update_status(record_id):
    try:
        new_status = request.json.get("status", "Done")
        service = get_sheets_service()
        result = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Evaluation Data Rowwise!A6:A").execute()
        ids = result.get('values', [])
        
        row_target = None
        for idx, row_id_list in enumerate(ids):
            if row_id_list and str(row_id_list[0]).isdigit() and int(row_id_list[0]) == record_id:
                row_target = idx + 6
                break

        if row_target:
            body = {'values': [[new_status]]}
            service.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"Evaluation Data Rowwise!P{row_target}",
                valueInputOption="RAW",
                body=body
            ).execute()
            sheets_cache.clear()  # Clear cache on write
            return {"success": True}
        else:
            return {"success": False, "error": f"Record with ID {record_id} not found"}, 404
    except Exception as e:
        return {"success": False, "error": str(e)}, 500

@app.route('/shoot_email/<int:record_id>', methods=['POST'])
def shoot_email(record_id):
    try:
        service = get_sheets_service()
        result = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Evaluation Data Rowwise!A6:P").execute()
        rows = result.get('values', [])
        
        job_row = None
        for idx, row in enumerate(rows):
            if row and str(row[0]).isdigit() and int(row[0]) == record_id:
                while len(row) < 16:
                    row.append("")
                job_row = row
                break
                
        if not job_row:
            return {"success": False, "error": f"Job #{record_id} not found"}, 404
            
        handler_name = job_row[2].strip()
        handler_email = job_row[3].strip()
        
        # Resilient lookup if email is missing in the row but handler name exists
        if not handler_email and handler_name:
            email_map = get_handler_email_map()
            handler_email = email_map.get(handler_name.lower(), f"{handler_name.lower().replace(' ', '')}@example.com")
            
        if not handler_email:
            return {"success": False, "error": "No email address found for this handler"}, 400
            
        job_details = {
            "id": job_row[0].strip(),
            "executive_name": job_row[1].strip(),
            "customer_details": job_row[4].strip(),
            "issue_type": job_row[5].strip(),
            "issue_date": job_row[6].strip(),
            "product_name": job_row[7].strip(),
            "deadline": job_row[14].strip(),
            "status": job_row[15].strip()
        }
        
        # Determine status description
        status_desc = "MANUAL NOTIFICATION"
        if job_details["status"].lower() == "done":
            status_desc = "RESOLVED (Manually Sent)"
        else:
            ist = pytz.timezone("Asia/Kolkata")
            today_dt = datetime.now(ist)
            clean_deadline = str(job_details["deadline"]).strip().split()[0]
            try:
                if "-" in clean_deadline and clean_deadline.index("-") == 4:
                    clean_deadline = datetime.strptime(clean_deadline, "%Y-%m-%d").strftime("%d-%m-%Y")
            except Exception:
                pass
                
            today_str = today_dt.strftime("%d-%m-%Y")
            day1_str = (today_dt + timedelta(days=1)).strftime("%d-%m-%Y")
            day2_str = (today_dt + timedelta(days=2)).strftime("%d-%m-%Y")
            
            if clean_deadline == today_str:
                status_desc = "CRITICAL: DUE TODAY"
            elif clean_deadline == day1_str:
                status_desc = "URGENT: 1 Day Remaining"
            elif clean_deadline == day2_str:
                status_desc = "WARNING: 2 Days Remaining"
            else:
                status_desc = f"PENDING (Due on {clean_deadline})"
        
        success = send_handler_email(handler_email, handler_name, job_details, status_desc)
        if success:
            return {"success": True}
        else:
            return {"success": False, "error": "Failed to dispatch email. Check SMTP configuration credentials on server."}, 500
    except Exception as e:
        return {"success": False, "error": str(e)}, 500

@app.before_request
def require_login():
    allowed_endpoints = ['login', 'static']
    if request.endpoint and request.endpoint not in allowed_endpoints and not session.get('authenticated'):
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('authenticated'):
        return redirect(url_for('evaluation_form'))
    if request.method == 'POST':
        password = request.form.get("password", "")
        if password == DASHBOARD_PASSWORD:
            session['authenticated'] = True
            flash("Successfully logged in!", "success")
            return redirect(url_for('evaluation_form'))
        else:
            flash("Invalid password, please try again.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    flash("Logged out successfully.", "success")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=True)