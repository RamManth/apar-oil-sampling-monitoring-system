# APAR – Oil Sample Monitoring System

An end-to-end digital operations portal developed for **APAR Industries** to streamline industrial oil sample logging, laboratory workflow delegation, target deadline tracking, and real-time ledger management.

---

## 📌 Overview

The **APAR Oil Sample Monitoring System** replaces manual, ad-hoc sample tracking with a centralized, responsive web platform. Designed primarily for industrial lubricant and transformer oil evaluations (such as the *APAR PowerOil* product lines), the system bridges field executives, technical handlers, and laboratory managers to ensure timely testing and reporting.

- **Live Application URL**: [apar-oil-sampling-monitoring-system-eight.vercel.app](https://apar-oil-sampling-monitoring-system-eight.vercel.app/)
- **Target Products**: Industrial lubricants, quenching oils, transformer oils, and specialty cutting oils.

---

## 🚀 Key Features

### 1. Sample Entry & Automated Deadlines
- **Personnel & Handler Allocation**: Logs the submitting executive and automatically maps the designated technical handler from APAR's laboratory team, complete with automated contact email lookup.
- **Dynamic SLA / Deadline Calculator**: Computes target completion dates based on issue profiles:
  | Issue Profile | Turnaround SLA | Target Purpose |
  | :--- | :--- | :--- |
  | **Complain Handling** | **+3 Days** | Critical customer resolution and failure analysis |
  | **Condition Monitoring** | **+7 Days** | Routine preventative maintenance and oil health checks |
  | **Product Benchmarking** | **+10 Days** | Comprehensive comparison vs. competitor specifications |
- **Detailed Sample Specifications**: Records machine source, collection points (sump/tank drain), sample volume, application type, competitor benchmarking details, and critical test parameters (e.g., cooling curve, viscosity, flash point).

### 2. Active Monitoring Ledger & Task Checklist
- **Tabular Ledger Interface**: Complete overview of all submitted jobs with unique Job IDs, customer names, assigned handlers, deadlines, and current statuses.
- **Interactive Job Management**:
  - Toggle between **Pending** and **Done** states with one click.
  - Quick-action buttons to dispatch email notifications directly to assigned handlers.
  - Real-time search filter by customer, handler, or status.
- **Client-Side Data Export**: Export active ledger records directly to formatted Excel spreadsheets using [SheetJS](https://sheetjs.com/) (`xlsx.full.min.js`).

### 3. Analytics & Workload Dashboard
- **Team Workload Allocation**: Embedded [Chart.js](https://www.chartjs.org/) bar chart visualising pending vs. completed sample evaluations across handlers.
- **KPI Summary Cards**: High-level counters tracking:
  - Total Registered Jobs
  - Active Pending Tasks
  - Completed Evaluations
  - Overdue / Alarm Alerts

### 4. Dynamic Ledger Synchronization
- Directly integrates with central Google Sheets backend storage to maintain a single real-time source of truth across field and lab personnel.

### 5. Developer Mode & Administrative Control Center
- **Dedicated Administrative Suite**: Accessible at `/developer` with secure administrator authentication.
- **Technical Handlers Management**: Live directory of laboratory testing personnel, automated email mapping, and real-time pending task workload tracking.
- **Portal User Directory**: Direct administrative management of system user accounts and credentials, with automated onboarding welcome emails dispatched via SMTP.
- **Direct Cloud Synchronization**: Live bidirectional syncing directly with Google Sheets backend storage.

---

## 📁 Repository Structure

```text
apar-oil-sampling-monitoring-system/
├── app.py                                              # Flask application server & API routes
├── requirements.txt                                    # Python dependencies
├── vercel.json                                         # Vercel serverless deployment config
├── api/
│   └── index.py                                        # Vercel serverless WSGI entrypoint
├── templates/
│   ├── form.html                                       # Main operations dashboard & sample logger
│   ├── login.html                                      # User profile authorization portal
│   ├── developer.html                                  # Developer Mode control center
│   ├── developer_login.html                            # Developer authentication gateway
│   ├── forgot_password.html                            # Password recovery request form
│   └── reset_password.html                             # Password reset token validation form
├── static/
│   └── apar_logo_dark.png                              # Dark-themed APAR brand logo
└── README.md                                           # Project documentation
```

---

## 🛠️ Technology Stack

- **Backend**: Python 3.9+, Flask
- **Frontend**: HTML5, Vanilla JavaScript, CSS3
- **CSS Framework**: Bootstrap 5
- **Visualizations**: [Chart.js](https://www.chartjs.org/)
- **Spreadsheet Processing**: [SheetJS (xlsx)](https://sheetjs.com/)
- **Hosting & Deployment**: [Vercel](https://vercel.com/)
- **Data Store**: Google Sheets / Microsoft Excel (`Monitoring Ledger`)

---

## 👨‍💻 Developer & Credits

- **Developer**: Ram Manthanwar
- **Email**: [rmanthanwar@yahoo.com](mailto:rmanthanwar@yahoo.com)
- **LinkedIn**: [linkedin.com/in/ram-manthanwar-072763216](https://www.linkedin.com/in/ram-manthanwar-072763216/)
- **GitHub**: [@RamManth](https://github.com/RamManth)