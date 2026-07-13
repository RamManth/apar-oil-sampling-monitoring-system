# Docker & Vercel Deployment Guide

This guide describes how to run the APAR Sample Evaluation Monitoring System inside a local **Docker container** or deploy it to **Vercel** as a serverless web application.

---

## 1. Deploying to Vercel

Vercel hosts the application as a **Python Serverless Function**. All requests to your custom domain or Vercel subdomain will be processed dynamically.

### How it Works
* **`vercel.json`**: Standardizes routes, using rewrites to redirect all HTTP requests (`/(.*)`) to the serverless function handler.
* **`api/index.py`**: Acts as the handler script that imports the Flask `app` instance from the main `app.py` in the root folder.
* **Statelessness**: Because serverless containers are ephemeral, in-memory states (like snoozing timestamps or temporary sessions) will not persist across different users or server wake-ups. However, because our primary data storage is **Google Sheets**, all records are perfectly persistent and shared!

### Step-by-Step Vercel Deployment

1. **Push Code to Git**: Push the project code to your Git provider (GitHub, GitLab, or Bitbucket).
2. **Create Vercel Project**:
   * Log in to the [Vercel Dashboard](https://vercel.com).
   * Click **New Project** and import your Git repository.
3. **Configure Environment Variables**:
   * Vercel will build the dependencies listed in `requirements.txt` automatically.
   * Under **Environment Variables**, you must add:
     * **Key**: `GOOGLE_SERVICE_ACCOUNT_JSON`
     * **Value**: Copy and paste the entire raw contents of your `credentials.json` file. It should look like:
       `{"type": "service_account", "project_id": "...", ...}`
   * *Note: The Flask `app.secret_key` will still automatically generate a secure key for each serverless session since it is set via `os.urandom(24)` in `app.py`.*
4. **Deploy**: Click **Deploy**. Vercel will automatically build the environment and host it at a generated URL (e.g., `https://your-project.vercel.app`).

---

## 2. Running in a Docker Container

Running inside Docker isolates the Flask server environment, ensuring consistency between development and production.

### Method A: Using Docker CLI
To build and run the container manually using the command line:

1. **Build the Docker Image**:
   ```bash
   docker build -t apar-monitoring-system .
   ```
2. **Run the Container**:
   * **Option 1: Using `credentials.json` file (recommended locally)**
     Mount your local credentials file directly to bypass environment setup:
     ```bash
     docker run -p 5001:5001 -v "$(pwd)/credentials.json:/app/credentials.json:ro" apar-monitoring-system
     ```
   * **Option 2: Using environment variable**
     Pass the credentials JSON string as a environment parameter:
     ```bash
     docker run -p 5001:5001 -e GOOGLE_SERVICE_ACCOUNT_JSON='{"type": "service_account", ...}' apar-monitoring-system
     ```

The app will start and be accessible at `http://localhost:5001`.

### Method B: Using Docker Compose
Docker Compose automates the container building and running workflow.

1. **Start the Service**:
   ```bash
   docker compose up --build
   ```
   *By default, the `docker-compose.yml` is configured to mount your local `credentials.json` directly.*

2. **Stop the Service**:
   ```bash
   docker compose down
   ```
