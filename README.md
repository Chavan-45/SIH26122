# SIH26122 - Intelligent Data Capture & Schedule-Linking Layer for Infrastructure Project Management

## About the Project

**SIH26122** is an infrastructure project execution platform designed to bridge high-level baseline project scheduling (e.g., Primavera / MS Project) with ground-level field progress updates across engineering disciplines (Civil, Piping, Electrical, Mechanical, Instrumentation, HSE).

---

## Current Status: Phase 3 (Project Creation, Project Access & Project Workspaces)

The platform currently includes:
- **Authentication & Roles**: Secure bcrypt password hashing, JWT Bearer tokens, and strict role segregation between **Lead Planners** and **Field Supervisors**.
- **Project Baseline Management**: Planners can create, view, and update infrastructure projects with codes, planned start/finish dates, and lifecycle statuses.
- **Team Allocation & Disciplines**: Planners can assign registered Supervisors to specific projects with discipline mappings (`CIVIL`, `PIPING`, `ELECTRICAL`, `MECHANICAL`, `INSTRUMENTATION`, `HSE`, `OTHER`).
- **Access Control & Scoping**: Supervisors only see and access projects to which they are assigned. Every project resource is strictly scoped and verified by `project_id`.
- **UI & Design System**: Approved Oil & Infrastructure Industrial Light Theme.

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
│   │   │   └── ProjectWorkspace.jsx    # Shared project context & team management
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
│   │   │   └── project_member.py       # ProjectMember ORM model
│   │   ├── schemas/
│   │   │   ├── user.py                 # User Pydantic schemas
│   │   │   └── project.py              # Project & Member Pydantic schemas
│   │   ├── services/
│   │   │   └── project_service.py      # Project access validation helpers
│   │   ├── routers/
│   │   │   ├── auth.py                 # Auth endpoints (/api/auth)
│   │   │   ├── test_roles.py           # Role testing endpoints (/api/test)
│   │   │   ├── projects.py             # Project CRUD & team endpoints (/api/projects)
│   │   │   └── users.py                # Supervisor lookup endpoint (/api/users)
│   │   └── main.py                     # FastAPI application entry point
│   ├── requirements.txt
│   └── .env.example
│
├── .gitignore
└── README.md
```

---

## API Endpoints (Phase 3)

### Authentication & Users
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/api/auth/register` | Public | Register a new user (`PLANNER` / `SUPERVISOR`) |
| `POST` | `/api/auth/login` | Public | Authenticate credentials and receive JWT |
| `GET` | `/api/auth/me` | Authenticated | Retrieve current user profile |
| `GET` | `/api/users/supervisors` | Planner only | Search registered supervisors for assignment |

### Infrastructure Projects
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/api/projects` | Planner only | Create a new infrastructure project |
| `GET` | `/api/projects` | Authenticated | List created (Planner) or assigned (Supervisor) projects |
| `GET` | `/api/projects/{id}` | Project members | Get detailed project overview |
| `PATCH` | `/api/projects/{id}` | Planner owner | Update project baseline metadata |
| `GET` | `/api/projects/{id}/members` | Project members | List project team and assigned disciplines |
| `POST` | `/api/projects/{id}/members` | Planner owner | Assign a registered supervisor with discipline |
| `DELETE` | `/api/projects/{id}/members/{user_id}` | Planner owner | Remove a supervisor from the project |

---

## Frontend Routes

| Route | Protection | Target Page |
|---|---|---|
| `/login` | Public | Sign In |
| `/register` | Public | Registration |
| `/planner` | Protected (`PLANNER`) | Planner Portal ("My Projects") |
| `/planner/projects/new` | Protected (`PLANNER`) | Create Infrastructure Project |
| `/supervisor` | Protected (`SUPERVISOR`) | Supervisor Portal ("Assigned Projects") |
| `/projects/:projectId` | Project Members | Shared Project Workspace |

---

## Startup Instructions

### 1. Backend
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- API Root: `http://localhost:8000`
- Interactive Swagger Docs: `http://localhost:8000/docs`

### 2. Frontend
```bash
cd frontend
npm run dev
```
- Frontend App: `http://localhost:5173`
- Production Build: `npm run build`
