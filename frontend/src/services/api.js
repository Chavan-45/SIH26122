/**
 * Centralized API configuration and service client for SIH26122.
 * The backend base URL is configured via environment variables (VITE_API_BASE_URL)
 * to avoid hardcoding throughout the application.
 */

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Checks the operational health of the FastAPI backend.
 * @returns {Promise<{success: boolean, data?: any, error?: string, timestamp: string}>}
 */
export async function checkBackendHealth() {
  const timestamp = new Date().toLocaleTimeString();
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    return {
      success: true,
      data,
      timestamp,
    };
  } catch (err) {
    return {
      success: false,
      error: err.message || 'Unable to connect to backend server',
      timestamp,
    };
  }
}
