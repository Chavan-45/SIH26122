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

/* ==========================================================================
   PROJECT APIs (Phase 3)
   ========================================================================== */

/**
 * Retrieve projects accessible to the authenticated user.
 */
export async function getProjects(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch projects (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Failed to load projects' };
  }
}

/**
 * Create a new infrastructure project (Planner only).
 */
export async function createProject(token, projectData) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(projectData),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Project creation failed (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to create project' };
  }
}

/**
 * Retrieve single project details with access control.
 */
export async function getProject(token, projectId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Project not found or access denied (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load project' };
  }
}

/**
 * Update project details (Planner owner only).
 */
export async function updateProject(token, projectId, updateData) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(updateData),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Project update failed (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to update project' };
  }
}

/**
 * Get project assigned team members (Supervisors).
 */
export async function getProjectMembers(token, projectId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/members`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch project members (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load project members' };
  }
}

/**
 * Assign a registered supervisor to a project (Planner owner only).
 */
export async function addProjectMember(token, projectId, { email, discipline }) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/members`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ email, discipline }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to assign supervisor (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to assign supervisor' };
  }
}

/**
 * Remove a supervisor from a project (Planner owner only).
 */
export async function removeProjectMember(token, projectId, userId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/members/${userId}`, {
      method: 'DELETE',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to remove supervisor (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to remove supervisor' };
  }
}

/**
 * Search registered supervisors for project assignment (Planner only).
 */
export async function getSupervisors(token, search = '') {
  try {
    const url = search
      ? `${API_BASE_URL}/api/users/supervisors?search=${encodeURIComponent(search)}`
      : `${API_BASE_URL}/api/users/supervisors`;

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to search supervisors (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load supervisors' };
  }
}
