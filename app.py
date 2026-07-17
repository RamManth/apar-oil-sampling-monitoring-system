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
from itsdangerous import URLSafeTimedSerializer
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

class SheetsCache:
    def __init__(self):
        self.data = {}
        self.last_fetched = {}
        self.lock = threading.Lock()
        
    def get(self, key, ttl_seconds=60):
        with self.lock:
            if key in self.data:
                if time.time() - self.last_fetched[key] < ttl_seconds:
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

sheets_cache = SheetsCache()


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

_sheets_service = None
_sheets_service_lock = threading.Lock()

def get_sheets_service():
    """Authenticates using environment variable or credentials.json and builds the Google Sheets connection."""
    global _sheets_service
    if _sheets_service is not None:
        return _sheets_service
        
    with _sheets_service_lock:
        if _sheets_service is None:
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
            _sheets_service = build('sheets', 'v4', credentials=creds, static_discovery=True).spreadsheets()
        return _sheets_service

def create_users_tab_if_missing(service, spreadsheet_id):
    """Checks if the Users tab exists. If not, creates it and adds default admin user."""
    try:
        sheet_metadata = service.get(spreadsheetId=spreadsheet_id).execute()
        sheets = sheet_metadata.get('sheets', [])
        tab_names = [s.get('properties', {}).get('title') for s in sheets]
        
        if "Users" not in tab_names:
            requests = [{
                'addSheet': {
                    'properties': {
                        'title': 'Users'
                    }
                }
            }]
            service.batchUpdate(spreadsheetId=spreadsheet_id, body={'requests': requests}).execute()
            
            # Write headers and default admin user credentials
            headers = [
                ["user", "password", "email"],
                ["admin", "admin123", SMTP_USERNAME or "admin@example.com"]
            ]
            service.values().update(
                spreadsheetId=spreadsheet_id,
                range="Users!A1:C2",
                valueInputOption="RAW",
                body={'values': headers}
            ).execute()
            print("Successfully created 'Users' tab with default admin user.")
    except Exception as e:
        print(f"⚠️ Error checking/creating 'Users' tab: {e}")

def get_users_list():
    """Fetches user credentials from Google Sheets Users tab."""
    cached_users = sheets_cache.get("users_list", ttl_seconds=300)
    if cached_users is not None:
        return cached_users
    
    users = []
    try:
        service = get_sheets_service()
        create_users_tab_if_missing(service, SPREADSHEET_ID)
        
        result = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Users!A2:C").execute()
        rows = result.get('values', [])
        for r in rows:
            if r and len(r) > 0 and str(r[0]).strip():
                username = str(r[0]).strip()
                password = str(r[1]).strip() if len(r) > 1 else ""
                email = str(r[2]).strip() if len(r) > 2 else ""
                
                # Dynamically generate password if empty in the Google Sheet
                if not password:
                    first_name = username.split()[0].replace('.', '').lower()
                    password = f"{first_name}123"
                    
                users.append({
                    "username": username,
                    "password": password,
                    "email": email
                })
        sheets_cache.set("users_list", users)
    except Exception as e:
        print(f"⚠️ Error loading users list: {e}")
        # Robust fallback default user so they don't get locked out
        users = [{"username": "admin", "password": "admin123", "email": SMTP_USERNAME or "admin@example.com"}]
    return users

def update_user_password_in_sheet(username, new_password):
    """Updates the password for the given user in Google Sheets."""
    try:
        service = get_sheets_service()
        # Fetch the entire column A to find the row index of the user
        result = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Users!A1:A100").execute()
        rows = result.get('values', [])
        
        row_target = None
        for idx, row in enumerate(rows):
            if row and row[0].strip().lower() == username.lower():
                row_target = idx + 1 # 1-indexed row number
                break
                
        if row_target:
            body = {'values': [[new_password]]}
            service.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"Users!B{row_target}",
                valueInputOption="RAW",
                body=body
            ).execute()
            sheets_cache.clear() # Clear cache so new password is loaded
            print(f"Successfully updated password for user '{username}' on row {row_target}.")
            return True
        else:
            print(f"⚠️ User '{username}' not found in sheet for password update.")
            return False
    except Exception as e:
        print(f"⚠️ Error updating password in Google Sheet: {e}")
        return False

def send_password_email(user_email, username, password, reset_link):
    """Sends an email with password recovery details and a reset link to the user."""
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print("⚠️ SMTP credentials not set. Skipping password recovery email.")
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "🔒 APAR Oil Sample Monitoring System - Password Recovery & Reset"
        msg['From'] = SENDER_EMAIL
        msg['To'] = user_email

        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; color: #1e293b; background-color: #f8fafc; margin: 0; padding: 20px; }}
                .container {{ max-width: 600px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
                .header {{ background-color: #111827; color: #ffffff; padding: 20px; text-align: center; }}
                .header h2 {{ margin: 0; font-size: 1.4rem; letter-spacing: 0.5px; text-transform: uppercase; }}
                .body {{ padding: 24px; }}
                .credentials-box {{ background-color: #f1f5f9; border: 1px solid #e2e8f0; padding: 16px; border-radius: 8px; margin: 20px 0; font-size: 1.1rem; }}
                .reset-btn-wrapper {{ text-align: center; margin: 30px 0; }}
                .btn-reset {{ background-color: #3b82f6; color: #ffffff !important; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: 600; display: inline-block; font-size: 0.95rem; box-shadow: 0 4px 6px rgba(59, 130, 246, 0.2); }}
                .btn-reset:hover {{ background-color: #2563eb; }}
                .link-text {{ font-size: 0.8rem; color: #64748b; word-break: break-all; }}
                .footer {{ background-color: #f8fafc; padding: 15px; text-align: center; font-size: 0.8rem; color: #64748b; border-top: 1px solid #e2e8f0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>APAR Oil Sample Monitoring System</h2>
                </div>
                <div class="body">
                    <p>Dear <strong>{username}</strong>,</p>
                    <p>We received a request to recover and reset the password for your account in the APAR Oil Sample Monitoring System.</p>
                    <p>Here are your current login credentials:</p>
                    <div class="credentials-box">
                        <strong>Username:</strong> <code style="color: #3b82f6;">{username}</code><br>
                        <strong>Password:</strong> <code style="color: #10b981;">{password}</code>
                    </div>
                    <p>To choose a new password, click the button below to secure your account:</p>
                    <div class="reset-btn-wrapper">
                        <a href="{reset_link}" class="btn-reset">Reset Your Password</a>
                    </div>
                    <p class="link-text">
                        If the button above does not work, copy and paste this URL into your browser:<br>
                        <a href="{reset_link}">{reset_link}</a>
                    </p>
                    <p style="margin-top: 25px; font-size: 0.85rem; color: #64748b; border-top: 1px solid #e2e8f0; padding-top: 15px;">
                        Please note: This link will expire in 1 hour. If you did not request this recovery, please inform the system administrator.
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
        server.sendmail(SENDER_EMAIL, user_email, msg.as_string())
        server.quit()
        print(f"📧 Recovery/Reset email successfully sent to {user_email} for user {username}")
        return True
    except Exception as e:
        print(f"❌ Failed to send recovery email to {user_email}: {e}")
        return False


def get_handler_email_map():
    """Fetches the handler email map from the Handlers Directory."""
    email_map = {}
    try:
        cached_rows = sheets_cache.get("handlers_directory", ttl_seconds=300)
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
        cached_rows = sheets_cache.get("evaluation_data_rows", ttl_seconds=60)
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
        cached_h_rows = sheets_cache.get("handlers_directory", ttl_seconds=300)
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

        cached_m_rows = sheets_cache.get("evaluation_data_rows", ttl_seconds=60)
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
        cached_rows = sheets_cache.get("evaluation_data_rows", ttl_seconds=60)
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
                "machine_collected": row[8].strip() if len(row) > 8 else "",
                "point_of_collection": row[9].strip() if len(row) > 9 else "",
                "quantity_sent": row[10].strip() if len(row) > 10 else "",
                "competitor_info": row[11].strip() if len(row) > 11 else "",
                "application_details": row[12].strip() if len(row) > 12 else "",
                "test_parameters": row[13].strip() if len(row) > 13 else "",
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
    days_mapping = {
        "Condition Monitoring": 7,
        "Complain Handling": 3,
        "Product Benchmarking": 10,
        "Ship Sample": 1,
        "Incoming Sample": 1
    }
    return (base_date + timedelta(days=days_mapping.get(issue_type, 0))).strftime("%d-%m-%Y")

@app.route('/', methods=['GET', 'POST'])
def evaluation_form():
    if request.args.get('force_refresh') == 'true':
        sheets_cache.clear()
        return redirect(url_for('evaluation_form'))

    if request.method == 'POST':
        service = get_sheets_service()
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

@app.route('/download_excel', methods=['POST'])
def download_excel():
    import base64
    from flask import make_response
    try:
        b64_data = request.form.get('base64_data')
        filename = request.form.get('filename', 'APAR_Oil_Sample_Ledger.xlsx')
        
        if not b64_data:
            return "No data provided", 400
            
        file_data = base64.b64decode(b64_data)
        response = make_response(file_data)
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        return f"Error processing download: {str(e)}", 500

def get_serializer():
    return URLSafeTimedSerializer(app.secret_key)

@app.before_request
def require_login():
    allowed_endpoints = ['login', 'static', 'forgot_password', 'reset_password']
    if request.endpoint and request.endpoint not in allowed_endpoints and not session.get('authenticated'):
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('authenticated'):
        return redirect(url_for('evaluation_form'))
        
    users = get_users_list()
    
    if request.method == 'POST':
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        authenticated = False
        user_email = ""
        for u in users:
            if u["username"].lower() == username.lower() and u["password"] == password:
                authenticated = True
                user_email = u["email"]
                break
                
        # Support fallback compatibility for the master admin
        if not authenticated and username.lower() == "admin" and password == DASHBOARD_PASSWORD:
            authenticated = True
            user_email = SMTP_USERNAME or "admin@example.com"
            
        if authenticated:
            session['authenticated'] = True
            session['username'] = username
            session['email'] = user_email
            flash("Successfully logged in!", "success")
            return redirect(url_for('evaluation_form', login='true'))
        else:
            flash("Invalid username or password, please try again.", "danger")
            
    return render_template('login.html', users=users)

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if session.get('authenticated'):
        return redirect(url_for('evaluation_form'))
        
    users = get_users_list()
    
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json() or {}
            username = data.get("username", "").strip()
        else:
            username = request.form.get("username", "").strip()
            
        if not username:
            if request.is_json:
                return {"success": False, "error": "Please select a user profile first."}, 400
            flash("Please select a user profile first.", "danger")
            return render_template('forgot_password.html', users=users)
            
        user_info = None
        for u in users:
            if u["username"].lower() == username.lower():
                user_info = u
                break
                
        if not user_info:
            if request.is_json:
                return {"success": False, "error": f"User '{username}' not found."}, 404
            flash(f"User '{username}' not found.", "danger")
            return render_template('forgot_password.html', users=users)
            
        email = user_info["email"]
        password = user_info["password"]
        
        if not email:
            if request.is_json:
                return {"success": False, "error": f"No email address configured for user '{username}'."}, 400
            flash(f"No email address configured for user '{username}'.", "danger")
            return render_template('forgot_password.html', users=users)
            
        # Generate secure timed password reset token
        serializer = get_serializer()
        token = serializer.dumps(username, salt='password-reset-salt')
        
        # Build absolute reset URL
        reset_link = url_for('reset_password', token=token, _external=True)
        
        # Dispatch recovery email
        success = send_password_email(email, username, password, reset_link)
        
        if success:
            msg = f"Reset instructions and current password successfully sent to {email}."
            if request.is_json:
                return {"success": True, "message": msg}
            flash(msg, "success")
            return redirect(url_for('login'))
        else:
            err = "Failed to send email. Check SMTP settings."
            if request.is_json:
                return {"success": False, "error": err}, 500
            flash(err, "danger")
            
    return render_template('forgot_password.html', users=users)

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if session.get('authenticated'):
        return redirect(url_for('evaluation_form'))
        
    token = request.args.get('token') or request.form.get('token')
    if not token:
        flash("Password reset token is missing.", "danger")
        return redirect(url_for('login'))
        
    serializer = get_serializer()
    try:
        # Link expires in 1 hour (3600 seconds)
        username = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except Exception:
        flash("The password reset link is invalid or has expired.", "danger")
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        new_password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        if not new_password:
            flash("Password cannot be empty.", "danger")
            return render_template('reset_password.html', token=token, username=username)
            
        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('reset_password.html', token=token, username=username)
            
        # Update in Google Sheets
        success = update_user_password_in_sheet(username, new_password)
        if success:
            flash("Password successfully reset! Please login with your new password.", "success")
            return redirect(url_for('login'))
        else:
            flash("Failed to update password in Google Sheet. Please try again later.", "danger")
            
    return render_template('reset_password.html', token=token, username=username)

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    flash("Logged out successfully.", "success")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=True)