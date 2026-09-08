# SIH26122 - Intelligent Data Capture & Schedule-Linking Layer for Infrastructure Project Management

## About the Project

**SIH26122** is an infrastructure project execution platform designed to bridge the gap between high-level project scheduling (L5/L6 schedules from Primavera / MS Project) and ground-level field progress reporting across civil, piping, electrical, mechanical, and instrumentation disciplines. The platform facilitates automated progress tracking, natural language updates, schedule alignment, and execution dashboards.

---

## Current Status: Phase 1 (Full-Stack Foundation)

This repository contains the clean, production-ready foundation for the project:
- **Backend**: FastAPI Python application providing modular REST endpoints with CORS and health monitoring.
- **Frontend**: React application built with Vite, featuring centralized environment-based API configuration and connection status monitoring.

---

## Project Structure

```text
SIH26122/
├── frontend/
│   ├── src/
│   │   ├── services/
│   │   │   └── api.js          # Centralized API service client
│   │   ├── App.jsx             # Main landing & status UI
│   │   ├── index.css           # Modern, professional UI styling
│   │   └── main.jsx            # React entry point
│   ├── public/                 # Static assets
│   ├── index.html              # HTML shell
│   ├── vite.config.js          # Vite configuration
│   ├── package.json            # Frontend dependencies and scripts
│   ├── .env.example            # Frontend environment template
│   └── .env                    # Frontend environment configuration
│
├── backend/
│   ├── app/
│   │   ├── __init__.py         # Python package marker
│   │   └── main.py             # FastAPI entry point, CORS & health check
│   ├── requirements.txt        # Python backend dependencies
│   └── .env.example            # Backend environment template
│
├── .gitignore                  # Git ignore rules
└── README.md                   # Project documentation
```

---

## Prerequisites

Ensure you have the following installed on your machine:
- **Python**: version `3.10` or higher
- **Node.js**: version `18.0` or higher
- **npm**: version `9.0` or higher

---

## Installation & Setup

### 1. Backend Setup (FastAPI)

1. Open a terminal and navigate to the backend directory:
   ```bash
   cd backend
   ```

2. (Recommended) Create and activate a Python virtual environment:
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   - **Linux / macOS**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. Install the required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. (Optional) Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```

5. Start the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

The backend will start at `http://localhost:8000`.

---

### 2. Frontend Setup (React + Vite)

1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install the frontend dependencies:
   ```bash
   npm install
   ```

3. Ensure `.env` exists with the backend API URL:
   ```text
   VITE_API_BASE_URL=http://localhost:8000
   ```

4. Start the Vite development server:
   ```bash
   npm run dev
   ```

5. To build the frontend for production:
   ```bash
   npm run build
   ```

---

## Development URLs

| Service | URL | Description |
|---|---|---|
| **Frontend App** | [http://localhost:5173](http://localhost:5173) | React user interface |
| **Backend API** | [http://localhost:8000](http://localhost:8000) | FastAPI server root |
| **Health Endpoint** | [http://localhost:8000/api/health](http://localhost:8000/api/health) | Backend health verification |
| **Interactive API Docs (Swagger)** | [http://localhost:8000/docs](http://localhost:8000/docs) | Auto-generated FastAPI documentation |
| **ReDoc API Docs** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Alternative API documentation |
