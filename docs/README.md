# APAR - Sample Evaluation Monitoring System

Welcome to the documentation for the **APAR Sample Evaluation Monitoring System**. This documentation provides a comprehensive overview of the application, its architecture, integration points, and setup instructions.

## Project Overview

The APAR Sample Evaluation Monitoring System is a web-based portal built with **Flask** (Python) that enables administrators and team leads to:
1. Log sample evaluation requests (referred to as Sample Evaluation Forms, or SEFs).
2. Dynamically assign these requests to specific handlers.
3. Track targets and auto-calculate deadlines based on the type of issue.
4. Prevent task overload by dynamically locking handlers who have pending tasks.
5. Trigger visual and audible alerts (alarms) for critical pending deadlines (due today, within 1 day, or within 2 days).
6. Sync all data in real-time with a centralized **Google Sheet**.

---

## Documentation Structure

For detailed explanations of the application's components, refer to the following pages in this folder:

1. **[Google Sheets & Integration Setup](google_sheets_setup.md)**
   * Guide to Google Sheets API structure, tabs, column configurations, and generating service account credentials (`credentials.json`).
2. **[Application Logic & Workflow](application_logic_workings.md)**
   * Technical breakdown of backend code, dynamic handler locking rules, deadline arithmetic, and the client-server alarm polling engine.
3. **[Docker & Vercel Deployment Guide](deployment.md)**
   * Deployment instructions for containerizing the Flask app or running it as a serverless service on Vercel.

---

## Technology Stack

* **Backend**: Python 3.x, Flask (web framework)
* **Frontend**: HTML5, Vanilla JavaScript, Bootstrap 5 (CSS framework), Google Fonts (Inter)
* **Storage & Synchronization**: Google Sheets API v4 (Service Account integration)
* **Audio Alerts**: Web Audio API (integrating a custom audio player with snooze logic)

---

## Directory Structure

```text
apar-oil-sampling-monitoring-system/
├── app.py                      # Main backend server and routing logic
├── credentials.json            # Google Service Account credentials (Private)
├── APAR_Sample_Evaluation_...  # Local copy/example of the evaluation data spreadsheet
├── Handlers_List.xlsx          # Local copy/example of the handler options
├── docs/                       # Project documentation
│   ├── README.md               # Main index (This file)
│   ├── google_sheets_setup.md  # Google Sheets setup instructions
│   └── application_logic_workings.md # Detailed breakdown of code logic
├── static/
│   └── apar_logo_dark.png      # Logo image asset used for themes/login
└── templates/
    └── form.html               # Frontend dashboard template (Bootstrap 5)
```

---

## Installation & Running Locally

### 1. Prerequisites
Ensure you have Python 3 installed. You will also need credentials for a Google Service Account (see [Google Sheets & Integration Setup](google_sheets_setup.md)).

### 2. Install Dependencies
You need Flask and Google API client libraries. Install them via `pip`:
```bash
pip install flask google-auth google-api-python-client
```

### 3. Setup Credentials
Ensure that your `credentials.json` file is placed in the project root folder.

### 4. Run the Server
Start the Flask application by running:
```bash
python app.py
```
The server will start on `http://127.0.0.1:5001/` with debug mode enabled. Open this URL in your web browser to access the portal.
