# Google Sheets Setup & Integration Guide

The APAR Sample Evaluation Monitoring System uses Google Sheets as its primary live database. This allows non-technical users to view and edit raw data directly in Google Sheets, while the Flask app manages submission validations, deadline calculations, and alerts.

---

## 1. Sheet Structure (Tabs & Schema)

The Google Sheet is identified by the `SPREADSHEET_ID` configuration variable in `app.py`:
* **Spreadsheet ID**: `1baRT4upMcOCyZjVSNsw0RLiT5A5z1MDfsTPYfyg35xo`

The workbook contains two essential tabs:

### Tab A: `Evaluation Data Rowwise`
This tab tracks all evaluation forms submitted through the web portal.
* **Start Range**: Data entries begin at row `6` (Range: `A6:O`). Rows 1–5 are typically reserved for headers or summaries.
* **Column Schema**:
  | Index | Column Letter | Field Name | Description / Example |
  |---|---|---|---|
  | `0` | **A** | **ID** | Numeric primary key (auto-incremented from current row count) |
  | `1` | **B** | **Executive Name** | Name of the logging executive |
  | `2` | **C** | **Allocated Handler** | Name of the assigned handler (from Handlers list) |
  | `3` | **D** | **Customer Details** | Segment / company details (e.g. `BAJAJ MOTORS LIMITED`) |
  | `4` | **E** | **Issue Type** | Profile category: `Condition Monitoring`, `Complain Handling`, `Product Benchmarking` |
  | `5` | **F** | **Issue Date** | Date of sampling formatted as `dd-mm-yyyy` |
  | `6` | **G** | **Product Full Name** | Brand/specification details of product (Competitor/APAR) |
  | `7` | **H** | **Machine Collected** | Machinery/furnace description where oil was sampled |
  | `8` | **I** | **Point of Collection** | Sump, tank drain, filter inlet, etc. |
  | `9` | **J** | **Quantity Sent** | Amount of oil sample (e.g., `2 Ltrs.`) |
  | `10` | **K** | **Competitor's Product Info** | Details on competitor specs or alternative oils |
  | `11` | **L** | **Application Details** | Type of application (e.g., `Quenching Oil`, `Gear Oil`) |
  | `12` | **M** | **Test Parameters** | Vital test remarks (e.g., `Viscosity at 40C, Water content`) |
  | `13` | **N** | **Target Deadline** | Autocalculated date when analysis is due (`dd-mm-yyyy`) |
  | `14` | **O** | **Status** | Status indicator: `Pending` or `Done` |

### Tab B: `Handlers Directory`
This tab acts as the master directory of all available handlers that can be assigned tasks.
* **Range**: Reads names starting from `A2` downwards (Range: `A2:A`).
* **Format**: A single column list of handler names.
* **Example**:
  ```text
  John Doe
  Jane Smith
  Bob Johnson
  ```

---

## 2. Setting Up Google Cloud Credentials

To authenticate the Python code with the Google Sheets API:

### Step 1: Create a Google Cloud Project
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g., `APAR-Sample-Evaluation-System`).

### Step 2: Enable APIs
1. Navigate to **APIs & Services > Library**.
2. Search for and enable **Google Sheets API**.
3. Search for and enable **Google Drive API**.

### Step 3: Create Service Account Credentials
1. Go to **APIs & Services > Credentials**.
2. Click **Create Credentials** and choose **Service Account**.
3. Fill in the Service Account name and details, then click **Create**.
4. Skip role selection (or set to *Viewer* / *Editor* if needed inside GCP) and finish creation.
5. In the Service Account list, click on the newly created account to edit it.
6. Go to the **Keys** tab, click **Add Key > Create new key**, and select **JSON** format.
7. Save the downloaded JSON file as **`credentials.json`** and place it in the root directory of this project.

### Step 4: Share the Google Sheet
1. Open your Google Sheet in a web browser.
2. Locate the service account email address (found inside the `client_email` field of your `credentials.json` or in GCP Console under IAM Credentials). It will look similar to:
   `your-service-account@your-project-id.iam.gserviceaccount.com`
3. Click the **Share** button on the top right of your Google Sheet.
4. Add the service account email as an **Editor** (so it can read/write data).
5. Uncheck "Notify people" and save.
