/**
 * Centralized API client service for KaryaSetu.
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

/* ==========================================================================
   PHASE 9 BATCH PROGRESS REPORT INGESTION APIs
   ========================================================================== */

/**
 * Preview spreadsheet columns and auto-detected mapping.
 */
export async function previewReportSpreadsheet(token, projectId, file) {
  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/progress-reports/preview-spreadsheet`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Spreadsheet preview failed (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to preview spreadsheet' };
  }
}

/**
 * Import spreadsheet progress report with column mapping.
 */
export async function importReportSpreadsheet(token, projectId, file, mapping = {}) {
  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('mapping_json', JSON.stringify(mapping));

    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/progress-reports/import-spreadsheet`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Spreadsheet import failed (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to import spreadsheet report' };
  }
}

/**
 * Import pasted free-text Daily Progress Report (DPR).
 */
export async function importReportText(token, projectId, rawText) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/progress-reports/import-text`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ raw_text: rawText }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Text report import failed (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to import text report' };
  }
}

/**
 * Import PDF document or scanned site image report (Phase 13).
 */
export async function importReportDocument(token, projectId, file) {
  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/progress-reports/import-document`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Document import failed (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to import document report' };
  }
}

/**
 * List all progress report import sessions for project.
 */
export async function getProgressReports(token, projectId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/progress-reports`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch progress reports (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load progress reports' };
  }
}

/**
 * Get progress report details and review items.
 */
export async function getProgressReport(token, projectId, reportId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/progress-reports/${reportId}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch progress report details (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load progress report' };
  }
}

/**
 * Approve or Reject an individual progress report item.
 */
export async function reviewReportItem(token, projectId, reportId, itemId, action) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/progress-reports/${reportId}/items/${itemId}/review`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ action }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Review action failed (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to update review status' };
  }
}

/**
 * Manually assign schedule activity to a progress report item.
 */
export async function selectReportItemActivity(token, projectId, reportId, itemId, activityId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/progress-reports/${reportId}/items/${itemId}/select-activity`, {
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
 * Approve all valid pending items in report session.
 */
export async function bulkApproveReportItems(token, projectId, reportId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/progress-reports/${reportId}/bulk-approve`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Bulk approve failed (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to bulk approve items' };
  }
}

/**
 * Apply all approved progress report items via existing Phase 5 execution service.
 */
export async function applyProgressReport(token, projectId, reportId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/progress-reports/${reportId}/apply`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Apply updates failed (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to apply progress updates' };
  }
}

/* ==========================================================================
   PHASE 10 PLANNER REVIEW CENTER APIs
   ========================================================================== */

/**
 * Get real DB summary counts for Planner Review Center cards (Planner only).
 */
export async function getPlannerReviewSummary(token, projectId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/review-center/summary`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch review summary (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load review summary' };
  }
}

/**
 * Get paginated list of field update review cases with filters (Planner only).
 */
export async function getPlannerReviewCases(
  token,
  projectId,
  { page = 1, pageSize = 50, status = 'ALL', source = 'ALL', discipline = 'ALL', confidence = 'ALL', search = '' } = {}
) {
  try {
    const queryParams = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
    });

    if (status && status !== 'ALL') queryParams.append('status', status);
    if (source && source !== 'ALL') queryParams.append('source', source);
    if (discipline && discipline !== 'ALL') queryParams.append('discipline', discipline);
    if (confidence && confidence !== 'ALL') queryParams.append('confidence', confidence);
    if (search && search.trim()) queryParams.append('search', search.trim());

    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/review-center?${queryParams.toString()}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch review cases (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load review cases' };
  }
}

/**
 * Get detailed review case with candidate activities and validation (Planner only).
 */
export async function getPlannerReviewCaseDetail(token, projectId, caseId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/review-center/${caseId}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch review case detail (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load review case detail' };
  }
}

/**
 * Link an existing schedule activity to the review case (Planner only).
 */
export async function selectPlannerReviewActivity(token, projectId, caseId, activityId, reviewReason = null) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/review-center/${caseId}/select-activity`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        activity_id: activityId,
        review_reason: reviewReason || null,
      }),
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
 * Reject a field update review case with reason (Planner only).
 */
export async function rejectPlannerReviewCase(token, projectId, caseId, reviewReason) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/review-center/${caseId}/reject`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        review_reason: reviewReason,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to reject case (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to reject case' };
  }
}

/**
 * Mark a field update as genuine unplanned work (Planner only).
 */
export async function markPlannerReviewUnplanned(token, projectId, caseId, reviewReason) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/review-center/${caseId}/mark-unplanned`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        review_reason: reviewReason,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to mark unplanned (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to mark unplanned' };
  }
}

/**
 * Apply resolved review case via Phase 5 execution service (Planner only).
 */
export async function applyPlannerReviewCase(token, projectId, caseId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/review-center/${caseId}/apply`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to apply review case (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to apply review case' };
  }
}

/* ==========================================================================
   PHASE 11: SCHEDULE SYNC & ACTUALS EXPORT BRIDGE API CLIENT
   ========================================================================== */

/**
 * Get summary KPI metrics for Schedule Sync & Export (Planner only).
 */
export async function getScheduleSyncSummary(token, projectId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/schedule-sync/summary`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch sync summary (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load sync summary' };
  }
}

/**
 * Preview canonical schedule actuals before export (Planner only).
 */
export async function previewScheduleSync(token, projectId, mode = 'FULL_SNAPSHOT') {
  try {
    const queryParams = new URLSearchParams({ mode });
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/schedule-sync/preview?${queryParams.toString()}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to preview export (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to preview schedule export' };
  }
}

/**
 * Create a persistent schedule actuals export snapshot (Planner only).
 */
export async function createScheduleExport(token, projectId, { exportMode = 'FULL_SNAPSHOT', fileFormat = 'XLSX' } = {}) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/schedule-sync/exports`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        export_mode: exportMode,
        file_format: fileFormat,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to create export snapshot (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to create schedule export' };
  }
}

/**
 * List all past schedule exports for a project (Planner only).
 */
export async function getScheduleExports(token, projectId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/schedule-sync/exports`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch export history (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load export history' };
  }
}

/**
 * Get details of a specific historical export snapshot (Planner only).
 */
export async function getScheduleExportDetail(token, projectId, exportId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/schedule-sync/exports/${exportId}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch export details (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load export details' };
  }
}

/**
 * Download historical CSV or XLSX export file directly from snapshot (Planner only).
 */
export async function downloadScheduleExport(token, projectId, exportId, defaultFileName) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/schedule-sync/exports/${exportId}/download`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      const errJson = await response.json().catch(() => ({}));
      throw new Error(errJson.detail || `Download failed (HTTP ${response.status})`);
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = defaultFileName || `export_${exportId}.xlsx`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);

    return { success: true };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to download export file' };
  }
}

/* ==========================================================================
   PHASE 12 — PROJECT ANALYTICS & FORECASTING API CLIENT
   ========================================================================== */

/**
 * Fetch top-level Analytics KPI summary and indicative completion metrics.
 */
export async function getAnalyticsSummary(token, projectId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/analytics/summary`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch analytics summary (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load analytics summary' };
  }
}

/**
 * Fetch reconstructed historical actual vs expected progress trend series (7d, 30d, 90d, all).
 */
export async function getAnalyticsTrend(token, projectId, range = '30d') {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/analytics/progress-trend?range=${encodeURIComponent(range)}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch progress trend (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load progress trend' };
  }
}

/**
 * Fetch discipline performance comparison metrics.
 */
export async function getAnalyticsDisciplines(token, projectId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/analytics/disciplines`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch discipline analytics (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load discipline analytics' };
  }
}

/**
 * Fetch rule-based schedule risk classification items with optional level/discipline filtering.
 */
export async function getAnalyticsRisks(token, projectId, { level, discipline } = {}) {
  try {
    const params = new URLSearchParams();
    if (level && level !== 'ALL') params.append('level', level);
    if (discipline && discipline !== 'ALL') params.append('discipline', discipline);

    const queryStr = params.toString() ? `?${params.toString()}` : '';
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/analytics/risks${queryStr}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch schedule risks (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load schedule risks' };
  }
}

/**
 * Fetch deterministic activity finish forecasts and project indicative completion.
 */
export async function getAnalyticsForecast(token, projectId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/analytics/forecast`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch activity forecasts (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load activity forecasts' };
  }
}

/**
 * Fetch completed activity schedule performance variance.
 */
export async function getAnalyticsCompleted(token, projectId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/analytics/completed-performance`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch completed performance (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load completed performance' };
  }
}

/**
 * ============================================================================
 * Phase 14: Institutional Project Memory & Historical Intelligence API
 * ============================================================================
 */

/**
 * Fetch project historical memory summary metrics.
 */
export async function getMemorySummary(token, projectId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/memory/summary`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch memory summary (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load project memory summary' };
  }
}

/**
 * Fetch paginated, filtered historical memory events.
 */
export async function getMemoryEvents(token, projectId, params = {}) {
  try {
    const queryParams = new URLSearchParams();
    if (params.q) queryParams.set('q', params.q);
    if (params.activity_id) queryParams.set('activity_id', params.activity_id);
    if (params.activity_code) queryParams.set('activity_code', params.activity_code);
    if (params.discipline && params.discipline !== 'ALL') queryParams.set('discipline', params.discipline);
    if (params.event_type && params.event_type !== 'ALL') queryParams.set('event_type', params.event_type);
    if (params.source && params.source !== 'ALL') queryParams.set('source', params.source);
    if (params.date_from) queryParams.set('date_from', params.date_from);
    if (params.date_to) queryParams.set('date_to', params.date_to);
    if (params.page) queryParams.set('page', params.page);
    if (params.page_size) queryParams.set('page_size', params.page_size);

    const qs = queryParams.toString();
    const url = `${API_BASE_URL}/api/projects/${projectId}/memory/events${qs ? `?${qs}` : ''}`;

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch memory events (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load memory events' };
  }
}

/**
 * Fetch chronological activity memory timeline, schedule context, and delay analysis.
 */
export async function getActivityMemoryTimeline(token, projectId, activityId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/memory/activities/${encodeURIComponent(activityId)}/timeline`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch activity memory timeline (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load activity timeline' };
  }
}

/**
 * Fetch deterministic activity delay classification and recorded notes.
 */
export async function getActivityDelayAnalysis(token, projectId, activityId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/memory/activities/${encodeURIComponent(activityId)}/delay-analysis`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to fetch delay analysis (HTTP ${response.status})`);
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Unable to load delay analysis' };
  }
}
