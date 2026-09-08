import os
import sys

# Set test environment
os.environ["DATABASE_URL"] = "sqlite:///./test_sih26122.db"
os.environ["JWT_SECRET_KEY"] = "sih26122-super-secure-jwt-secret-key-for-infrastructure-project-management-2026-phase2"

# Clean old test db if present
if os.path.exists("./test_sih26122.db"):
    try:
        os.remove("./test_sih26122.db")
    except Exception:
        pass

from fastapi.testclient import TestClient
from app.main import app
from app.database.database import Base, engine, SessionLocal
from app.models.user import User

# Initialize tables
Base.metadata.create_all(bind=engine)

client = TestClient(app)

print("--- STARTING PHASE 2 AUTOMATED TEST SUITE ---")

# TEST 1: Register Planner
res1 = client.post(
    "/api/auth/register",
    json={
        "full_name": "Planner Test",
        "email": "planner@test.com",
        "password": "password123",
        "role": "PLANNER",
    },
)
print(f"TEST 1 - Register Planner: Status {res1.status_code}")
assert res1.status_code == 201, f"Expected 201, got {res1.status_code}: {res1.text}"
user1_data = res1.json()
assert user1_data["email"] == "planner@test.com"
assert user1_data["role"] == "PLANNER"
assert "hashed_password" not in user1_data, "hashed_password leaked in response!"

# Verify password hashed in database
db = SessionLocal()
db_user = db.query(User).filter(User.email == "planner@test.com").first()
assert db_user is not None
assert db_user.hashed_password != "password123", "Password was stored in plaintext!"
assert db_user.hashed_password.startswith("$2b$") or db_user.hashed_password.startswith("$2a$"), "Not a valid bcrypt hash!"
db.close()
print("TEST 1 PASSED: Planner registered, password securely bcrypt hashed in DB.")

# TEST 2: Register Supervisor
res2 = client.post(
    "/api/auth/register",
    json={
        "full_name": "Supervisor Test",
        "email": "supervisor@test.com",
        "password": "password123",
        "role": "SUPERVISOR",
    },
)
print(f"TEST 2 - Register Supervisor: Status {res2.status_code}")
assert res2.status_code == 201, f"Expected 201, got {res2.status_code}: {res2.text}"
user2_data = res2.json()
assert user2_data["email"] == "supervisor@test.com"
assert user2_data["role"] == "SUPERVISOR"
print("TEST 2 PASSED: Supervisor registered successfully.")

# TEST 3: Duplicate Registration Rejection
res3 = client.post(
    "/api/auth/register",
    json={
        "full_name": "Duplicate Planner",
        "email": "planner@test.com",
        "password": "password123",
        "role": "PLANNER",
    },
)
print(f"TEST 3 - Duplicate Email Rejection: Status {res3.status_code}")
assert res3.status_code == 400, f"Expected 400, got {res3.status_code}: {res3.text}"
print("TEST 3 PASSED: Duplicate email correctly rejected with 400 Bad Request.")

# TEST 4: Login as Planner
res4 = client.post(
    "/api/auth/login",
    json={
        "email": "planner@test.com",
        "password": "password123",
    },
)
print(f"TEST 4 - Login as Planner: Status {res4.status_code}")
assert res4.status_code == 200, f"Expected 200, got {res4.status_code}: {res4.text}"
login4_data = res4.json()
assert "access_token" in login4_data
planner_token = login4_data["access_token"]
assert login4_data["user"]["role"] == "PLANNER"
print("TEST 4 PASSED: Planner login successful, JWT token received.")

# TEST 5: Login as Supervisor
res5 = client.post(
    "/api/auth/login",
    json={
        "email": "supervisor@test.com",
        "password": "password123",
    },
)
print(f"TEST 5 - Login as Supervisor: Status {res5.status_code}")
assert res5.status_code == 200, f"Expected 200, got {res5.status_code}: {res5.text}"
login5_data = res5.json()
assert "access_token" in login5_data
supervisor_token = login5_data["access_token"]
assert login5_data["user"]["role"] == "SUPERVISOR"
print("TEST 5 PASSED: Supervisor login successful, JWT token received.")

# TEST 6: Planner token on GET /api/test/planner -> 200
res6 = client.get(
    "/api/test/planner",
    headers={"Authorization": f"Bearer {planner_token}"},
)
print(f"TEST 6 - Planner token -> /api/test/planner: Status {res6.status_code}")
assert res6.status_code == 200, f"Expected 200, got {res6.status_code}: {res6.text}"
print("TEST 6 PASSED: Planner authorized to access /api/test/planner.")

# TEST 7: Supervisor token on GET /api/test/planner -> 403
res7 = client.get(
    "/api/test/planner",
    headers={"Authorization": f"Bearer {supervisor_token}"},
)
print(f"TEST 7 - Supervisor token -> /api/test/planner: Status {res7.status_code}")
assert res7.status_code == 403, f"Expected 403, got {res7.status_code}: {res7.text}"
print("TEST 7 PASSED: Supervisor correctly denied access to Planner resource (403 Forbidden).")

# TEST 8: Supervisor token on GET /api/test/supervisor -> 200
res8 = client.get(
    "/api/test/supervisor",
    headers={"Authorization": f"Bearer {supervisor_token}"},
)
print(f"TEST 8 - Supervisor token -> /api/test/supervisor: Status {res8.status_code}")
assert res8.status_code == 200, f"Expected 200, got {res8.status_code}: {res8.text}"
print("TEST 8 PASSED: Supervisor authorized to access /api/test/supervisor.")

# TEST 9: No token on GET /api/auth/me -> 401
res9 = client.get("/api/auth/me")
print(f"TEST 9 - No token -> /api/auth/me: Status {res9.status_code}")
assert res9.status_code == 401, f"Expected 401, got {res9.status_code}: {res9.text}"
print("TEST 9 PASSED: Unauthenticated request rejected with 401 Unauthorized.")

# TEST 10: Valid token on GET /api/auth/me -> 200
res10 = client.get(
    "/api/auth/me",
    headers={"Authorization": f"Bearer {planner_token}"},
)
print(f"TEST 10 - Valid token -> /api/auth/me: Status {res10.status_code}")
assert res10.status_code == 200, f"Expected 200, got {res10.status_code}: {res10.text}"
assert res10.json()["email"] == "planner@test.com"
print("TEST 10 PASSED: Authenticated user profile restored successfully.")

# TEST 11: Invalid/Tampered Token on GET /api/auth/me -> 401
res11 = client.get(
    "/api/auth/me",
    headers={"Authorization": "Bearer invalid.tampered.token"},
)
print(f"TEST 11 - Tampered token -> /api/auth/me: Status {res11.status_code}")
assert res11.status_code == 401, f"Expected 401, got {res11.status_code}: {res11.text}"
print("TEST 11 PASSED: Tampered token rejected with 401 Unauthorized.")

# TEST 13: GET /api/health still works -> 200
res13 = client.get("/api/health")
print(f"TEST 13 - Health check -> /api/health: Status {res13.status_code}")
assert res13.status_code == 200, f"Expected 200, got {res13.status_code}: {res13.text}"
assert res13.json() == {"status": "ok", "service": "SIH26122 Backend"}
print("TEST 13 PASSED: Health check endpoint working as expected.")

# Clean up test DB
engine.dispose()
if os.path.exists("./test_sih26122.db"):
    try:
        os.remove("./test_sih26122.db")
    except Exception:
        pass

print("\n--- ALL BACKEND AUTOMATED TESTS PASSED SUCCESSFULLY! (100% PASS) ---")
