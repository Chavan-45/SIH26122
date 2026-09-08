/**
 * Centralized API client service for SIH26122.
 * The backend base URL is dynamically loaded from environment variables (VITE_API_BASE_URL).
 */

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Checks the operational health of the FastAPI backend.
 */
export async function checkBackendHealth() {
  const timestamp = new Date().toLocaleTimeString();
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    return { success: true, data, timestamp };
  } catch (err) {
    return {
      success: false,
      error: err.message || 'Unable to connect to backend server',
      timestamp,
    };
  }
}

/**
 * Register a new user (PLANNER or SUPERVISOR).
 */
export async function registerUser({ fullName, email, password, role }) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        full_name: fullName,
        email,
        password,
        role,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Registration failed (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Registration failed' };
  }
}

/**
 * Authenticate user credentials and retrieve JWT token.
 */
export async function loginUser(email, password) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Authentication failed (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Login failed' };
  }
}

/**
 * Fetch current authenticated user profile using stored JWT token.
 */
export async function getMe(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Session expired or invalid (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Failed to fetch user session' };
  }
}

/**
 * Test endpoint for PLANNER role verification.
 */
export async function testPlannerRole(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/test/planner`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    return { status: response.status, data };
  } catch (err) {
    return { status: 500, error: err.message };
  }
}

/**
 * Test endpoint for SUPERVISOR role verification.
 */
export async function testSupervisorRole(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/test/supervisor`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    return { status: response.status, data };
  } catch (err) {
    return { status: 500, error: err.message };
  }
}
