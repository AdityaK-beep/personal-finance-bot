# Personal Finance Advisor Bot

An autonomous, full-stack personal finance web application with AI advisory capabilities powered by Google Gemini and a deterministic financial heuristics engine.

## Features

- **Secure Authentication:** User registration, password hashing (`werkzeug.security`), session management (`Flask-Login`), and strict user data isolation.
- **Financial Tracking:** Real-time income and expense tracking, categorical tagging (Rent, Groceries, Transport, Entertainment, Utilities, Other).
- **Budgeting & Savings Targets:** Set monthly budget limits and target savings rates with visual progress utilization and overage alerts.
- **Interactive Analytics:** Responsive Chart.js doughnut chart breaking down monthly expenditure by category.
- **AI Financial Advisory:** In-depth financial diagnostics, 50/30/20 budget framework comparisons, overspending detection, and persona-specific recommendations (Salaried, Student, Freelancer, Household Manager).
- **Zero-Downtime Fallback:** Works seamlessly even without an API key through a built-in deterministic heuristic analysis engine.

---

## Tech Stack

- **Backend:** Python 3.11+, Flask 3.x, Flask-SQLAlchemy, Flask-Login, Werkzeug, python-dotenv, google-genai, Gunicorn
- **Database:** SQLite (ORM-managed via SQLAlchemy)
- **Frontend:** HTML5, Jinja2, Vanilla CSS3, Bootstrap 5.3 CDN, Chart.js CDN

---

## Local Development

### 1. Clone & Setup
```bash
git clone <your-repo-url>
cd personal-finance-bot
python -m venv .venv
```

**Windows:**
```powershell
.venv\Scripts\activate
```

**macOS/Linux:**
```bash
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` to specify your `SECRET_KEY` and optional `GEMINI_API_KEY`:
```env
SECRET_KEY=your-random-production-secret-key
GEMINI_API_KEY=your-gemini-api-key
```

### 4. Run the Application
```bash
python run.py
```
Open **http://127.0.0.1:5000** in your browser.

---

## Running Automated Tests

```bash
python -m unittest tests/test_suite.py
```

---

## Cloud Deployment Guide

### Option 1: Render (Recommended - Free Tier)

1. Push your repository to GitHub.
2. Sign in to [Render](https://render.com).
3. Click **New +** -> **Web Service**.
4. Connect your GitHub repository.
5. Configure settings:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn run:app`
6. Add Environment Variables:
   - `SECRET_KEY`: (Generate a secure random string)
   - `GEMINI_API_KEY`: (Your Google Gemini API Key)
   - `FLASK_DEBUG`: `0`
7. Click **Create Web Service**.

*(Alternatively, Render will automatically detect `render.yaml` for 1-click deployment!)*

### Option 2: Railway

1. Sign in to [Railway](https://railway.app).
2. Click **New Project** -> **Deploy from GitHub repo**.
3. Select your repository.
4. Set environment variables (`SECRET_KEY`, `GEMINI_API_KEY`) in the Railway dashboard.
5. Railway will automatically detect the `Procfile` and deploy.

### Option 3: Docker Container

Build and run anywhere with Docker:
```bash
docker build -t personal-finance-bot .
docker run -p 5000:5000 -e SECRET_KEY="mysecret" -e GEMINI_API_KEY="mykey" personal-finance-bot
```
