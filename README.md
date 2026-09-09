# SIH26122 - Intelligent Data Capture & Schedule-Linking Layer for Infrastructure Project Management

## About the Project

**SIH26122** is an infrastructure project execution platform designed to bridge high-level baseline project scheduling (e.g., Primavera P6 / MS Project) with ground-level field progress updates across engineering disciplines (Civil, Piping, Electrical, Mechanical, Instrumentation, HSE).

---

## Current Status: Phase 4 (L5/L6 Schedule Import & Activity Database)

The platform currently includes:
- **Authentication & Roles**: Secure bcrypt password hashing, JWT Bearer tokens, and strict role segregation between **Lead Planners** and **Field Supervisors**.
- **Project Baseline Management**: Planners can create, view, and update infrastructure projects with codes, planned start/finish dates, and lifecycle statuses.
- **Team Allocation & Disciplines**: Planners can assign registered Supervisors to specific projects with discipline mappings (`CIVIL`, `PIPING`, `ELECTRICAL`, `MECHANICAL`, `INSTRUMENTATION`, `HSE`, `OTHER`).
- **L5/L6 Baseline Schedule Import**: Planners can upload structured project schedule exports (.csv and .xlsx) from Primavera P6 or MS Project.
- **Preview & Auto Column Mapping**: Interactive 2-step import wizard that auto-detects column headers using case-insensitive alias matching (e.g. `Activity ID`, `Task Name`, `Start Date`, `Baseline Finish`), validates dates (`finish >= start`), and previews rows before commit.
- **Transactional Database Safety**: Atomic single-transaction database commit ensures that if any row has validation errors or duplicate activity codes, 0 activities are inserted.
- **Structured Activity Database**: Activities stored in the `activities` table with unique constraint `(project_id, activity_code)` and audit logs in `schedule_imports`.
- **Filtered Schedule Workspace & Read-Only Access**: Full schedule workspace with search, discipline filter, schedule level filter (L5, L6), pagination, and activity detail drawer. Supervisors have strict read-only access.
- **UI & Design System**: Approved Oil & Infrastructure Industrial Light Theme.

---

## Supported Schedule Import Formats & Fields

### Formats
- `.csv` (Comma Separated Values)
- `.xlsx` (Microsoft Excel Spreadsheet)

### Required Canonical Fields
- `activity_code` (e.g. `CIV-001`, `PIP-102`)
- `activity_name` (e.g. `Site Excavation`, `Pipe Spool Erection`)
- `planned_start` (e.g. `2026-10-01`)
- `planned_finish` (e.g. `2026-10-15`)

### Optional Fields
- `wbs_code` (e.g. `1.2.4.1`)
- `wbs_name`
- `schedule_level` (e.g. `L5`, `L6`)
- `discipline` (Civil, Piping, Electrical, Mechanical, Instrumentation, HSE, Other, or `UNASSIGNED`)
- `planned_duration` (Numeric duration)
- `predecessors` (Textual predecessor IDs)

---

## Project Structure

```text
SIH26122/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Navbar.jsx              # Authenticated navigation bar
│   │   │   └── ProtectedRoute.jsx      # Role-based route guard
│   │   ├── context/
│   │   │   └── AuthContext.jsx         # Auth state & token persistence
│   │   ├── pages/
│   │   │   ├── LoginPage.jsx           # Sign-in page
│   │   │   ├── RegisterPage.jsx        # Registration with role selector
│   │   │   ├── PlannerWorkspace.jsx    # Planner portal with "My Projects"
│   │   │   ├── CreateProjectPage.jsx   # Project creation form
│   │   │   ├── SupervisorWorkspace.jsx # Supervisor portal with "Assigned Projects"
│   │   │   └── ProjectWorkspace.jsx    # Overview, Schedule table, Multi-step Import, Team
│   │   ├── services/
│   │   │   └── api.js                  # Centralized API service client
│   │   ├── App.jsx                     # Route definitions
│   │   ├── index.css                   # Industrial Light Design System
│   │   └── main.jsx                    # React mounting entry point
│   ├── package.json
│   └── vite.config.js
│
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py               # Environment configuration
│   │   │   ├── dependencies.py         # Auth & RBAC dependencies
│   │   │   └── security.py             # Bcrypt hashing & JWT utilities
│   │   ├── database/
│   │   │   └── database.py             # SQLAlchemy engine & session generator
│   │   ├── models/
│   │   │   ├── user.py                 # User ORM model
│   │   │   ├── project.py              # Project ORM model
│   │   │   ├── project_member.py       # ProjectMember ORM model
│   │   │   ├── activity.py             # L5/L6 Activity ORM model
│   │   │   └── schedule_import.py      # ScheduleImport audit ORM model
│   │   ├── schemas/
│   │   │   ├── user.py                 # User Pydantic schemas
│   │   │   ├── project.py              # Project & Member Pydantic schemas
│   │   │   └── activity.py             # Activity & Schedule Pydantic schemas
│   │   ├── services/
│   │   │   ├── project_service.py      # Project access validation helpers
│   │   │   └── schedule_service.py     # CSV/XLSX parsing, alias detection & import service
│   │   ├── routers/
│   │   │   ├── auth.py                 # Auth endpoints (/api/auth)
│   │   │   ├── test_roles.py           # Role testing endpoints (/api/test)
│   │   │   ├── projects.py             # Project CRUD & team endpoints (/api/projects)
│   │   │   ├── schedule.py             # Schedule upload, preview, import & activity listing
│   │   │   └── users.py                # Supervisor lookup endpoint (/api/users)
│   │   └── main.py                     # FastAPI application entry point
│   ├── tests/
│   │   └── fixtures/                   # Sample schedule CSV and XLSX fixtures
│   ├── test_phase4.py                  # Isolated automated test suite
│   ├── requirements.txt
│   └── .env.example
│
├── .gitignore
└── README.md
```

---

## API Endpoints (Phase 4)

### Authentication & Users
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/api/auth/register` | Public | Register a new user (`PLANNER` / `SUPERVISOR`) |
| `POST` | `/api/auth/login` | Public | Authenticate credentials and receive JWT |
| `GET` | `/api/auth/me` | Authenticated | Retrieve current user profile |
| `GET` | `/api/users/supervisors` | Planner only | Search registered supervisors for assignment |

### Infrastructure Projects & Members
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/api/projects` | Planner only | Create a new infrastructure project |
| `GET` | `/api/projects` | Authenticated | List created (Planner) or assigned (Supervisor) projects |
| `GET` | `/api/projects/{id}` | Project members | Get detailed project overview |
| `PATCH` | `/api/projects/{id}` | Planner owner | Update project baseline metadata |
| `GET` | `/api/projects/{id}/members` | Project members | List project team and assigned disciplines |
| `POST` | `/api/projects/{id}/members` | Planner owner | Assign a registered supervisor with discipline |
| `DELETE` | `/api/projects/{id}/members/{user_id}` | Planner owner | Remove a supervisor from the project |

### Schedule Import & Activity Database (Phase 4)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/api/projects/{id}/schedule/preview` | Planner owner | Upload and preview CSV/XLSX schedule with auto column header mapping |
| `POST` | `/api/projects/{id}/schedule/import` | Planner owner | Confirm and commit baseline schedule import (Single transaction) |
| `GET` | `/api/projects/{id}/schedule` | Project members | Get schedule metadata, import audit log, date range, and discipline/level distributions |
| `GET` | `/api/projects/{id}/activities` | Project members | Paginated activity listing with search, discipline, and level filters |
| `GET` | `/api/projects/{id}/activities/{act_id}` | Project members | Get single activity details |

---

## Frontend Routes

| Route | Protection | Target Page |
|---|---|---|
| `/login` | Public | Sign In |
| `/register` | Public | Registration |
| `/planner` | Protected (`PLANNER`) | Planner Portal ("My Projects") |
| `/planner/projects/new` | Protected (`PLANNER`) | Create Infrastructure Project |
| `/supervisor` | Protected (`SUPERVISOR`) | Supervisor Portal ("Assigned Projects") |
| `/projects/:projectId` | Project Members | Shared Project Workspace (Overview, Schedule, Team) |

---

## Startup Instructions

### 1. Backend
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- API Root: `http://localhost:8000`
- Interactive Swagger Docs: `http://localhost:8000/docs`
- Run Phase 4 Automated Test Suite: `python test_phase4.py`

### 2. Frontend
```bash
cd frontend
npm run dev
```
- Frontend App: `http://localhost:5173`
- Production Build: `npm run build`

