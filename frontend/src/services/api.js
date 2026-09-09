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

/* ==========================================================================
   SCHEDULE & ACTIVITY APIs (Phase 4)
   ========================================================================== */

/**
 * Preview schedule baseline file import (Planner owner only).
 */
export async function previewSchedule(token, projectId, file) {
  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/schedule/preview`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      const errDetail = typeof data.detail === 'string' ? data.detail : data.detail?.message || 'Schedule preview failed';
      throw new Error(errDetail);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to preview schedule' };
  }
}

/**
 * Confirm and execute baseline schedule import (Planner owner only).
 */
export async function importSchedule(token, projectId, file, mapping) {
  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('mapping', JSON.stringify(mapping));

    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/schedule/import`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      let msg = 'Schedule import failed';
      if (typeof data.detail === 'string') {
        msg = data.detail;
      } else if (data.detail && typeof data.detail === 'object') {
        if (data.detail.errors && Array.isArray(data.detail.errors)) {
          msg = data.detail.errors.join(' | ');
        } else if (data.detail.message) {
          msg = data.detail.message;
        }
      }
      throw new Error(msg);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to import schedule' };
  }
}

/**
 * Get project schedule status and metadata (Authorized users).
 */
export async function getScheduleStatus(token, projectId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/schedule`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch schedule status (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load schedule status' };
  }
}

/**
 * Get paginated activities with search and discipline/level filters (Authorized users).
 */
export async function getActivities(token, projectId, { page = 1, pageSize = 50, search = '', discipline = 'ALL', scheduleLevel = 'ALL' } = {}) {
  try {
    const queryParams = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
    });

    if (search) queryParams.append('search', search);
    if (discipline && discipline !== 'ALL') queryParams.append('discipline', discipline);
    if (scheduleLevel && scheduleLevel !== 'ALL') queryParams.append('schedule_level', scheduleLevel);

    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/activities?${queryParams.toString()}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch activities (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load activities' };
  }
}

/**
 * Get single activity details (Authorized users).
 */
export async function getActivity(token, projectId, activityId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/activities/${activityId}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Activity not found (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load activity detail' };
  }
}

/* ==========================================================================
   ACTUAL EXECUTION & PROGRESS TRACKING APIs (Phase 5)
   ========================================================================== */

/**
 * Submit progress update / status transition for an activity (Authorized Planner or Discipline Supervisor).
 */
export async function reportActivityProgress(token, projectId, activityId, { updateType, reportedDate, progressPercentage, remarks }) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/activities/${activityId}/progress`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        update_type: updateType,
        reported_date: reportedDate,
        progress_percentage: progressPercentage,
        remarks: remarks || null,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Progress report failed (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to submit progress report' };
  }
}

/**
 * Get current execution state and variance metrics for an activity.
 */
export async function getActivityExecution(token, projectId, activityId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/activities/${activityId}/execution`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Execution state not found (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load execution state' };
  }
}

/**
 * Get append-only audit trail of progress updates for an activity.
 */
export async function getActivityProgressHistory(token, projectId, activityId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/activities/${activityId}/progress-history`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Progress history not found (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load progress history' };
  }
}

/**
 * Get high-level execution summary for project dashboard.
 */
export async function getExecutionSummary(token, projectId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/execution-summary`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Execution summary failed (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load execution summary' };
  }
}

/* ==========================================================================
   PROJECT DASHBOARD APIs (Phase 6)
   ========================================================================== */

/**
 * Retrieve 100% database-derived project control dashboard metrics (Authorized users).
 */
export async function getProjectDashboard(token, projectId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/dashboard`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch project dashboard (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load project dashboard' };
  }
}

/* ==========================================================================
   PROJECT AI ASSISTANT APIs (Phase 7)
   ========================================================================== */

/**
 * Send an operational query to the Project AI Assistant.
 */
export async function sendAIChatMessage(token, projectId, { conversationId = null, prompt }) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/ai/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        conversation_id: conversationId,
        prompt,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `AI Chat request failed (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to connect to AI Assistant' };
  }
}

/**
 * Retrieve list of AI conversation sessions for current user in project.
 */
export async function getAIConversations(token, projectId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/ai/conversations`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch AI conversations (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load AI conversations' };
  }
}

/**
 * Get message history for a specific AI conversation session.
 */
export async function getAIConversation(token, projectId, conversationId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/ai/conversations/${conversationId}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch AI conversation history (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load AI conversation history' };
  }
}

/**
 * Delete an AI conversation session and its message history.
 */
export async function deleteAIConversation(token, projectId, conversationId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/ai/conversations/${conversationId}`, {
      method: 'DELETE',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to delete conversation (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to delete conversation' };
  }
}

/* ==========================================================================
   PHASE 8 NATURAL-LANGUAGE EXECUTION REPORT DRAFT APIs
   ========================================================================== */

/**
 * Confirm an AI-generated execution report draft and apply progress update.
 */
export async function confirmAIDraft(token, projectId, draftId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/ai/progress-drafts/${draftId}/confirm`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to confirm progress update (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to confirm progress update' };
  }
}

/**
 * Cancel/reject an AI-generated execution report draft.
 */
export async function cancelAIDraft(token, projectId, draftId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/ai/progress-drafts/${draftId}/cancel`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to cancel draft (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to cancel draft' };
  }
}

/**
 * Manually assign schedule activity to execution report draft.
 */
export async function selectAIDraftActivity(token, projectId, draftId, activityId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/ai/progress-drafts/${draftId}/select-activity`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ activity_id: activityId }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to link activity (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to link activity' };
  }
}

/**
 * Flag unmatched execution report draft for Planner Review.
 */
export async function flagAIDraftPlannerReview(token, projectId, draftId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/ai/progress-drafts/${draftId}/flag-planner-review`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to flag for review (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to flag for review' };
  }
}

/**
 * Retrieve execution report draft details.
 */
export async function getAIDraft(token, projectId, draftId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/ai/progress-drafts/${draftId}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch draft (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load draft' };
  }
}




