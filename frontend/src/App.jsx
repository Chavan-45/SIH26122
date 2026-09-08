import React, { useState, useEffect, useCallback } from 'react';
import { checkBackendHealth, API_BASE_URL } from './services/api';
import { Activity, Server, RefreshCw, CheckCircle2, XCircle, Layers } from 'lucide-react';

export default function App() {
  const [healthStatus, setHealthStatus] = useState({
    loading: true,
    connected: false,
    data: null,
    error: null,
    timestamp: null,
  });

  const fetchHealth = useCallback(async () => {
    setHealthStatus(prev => ({ ...prev, loading: true }));
    const result = await checkBackendHealth();

    if (result.success) {
      setHealthStatus({
        loading: false,
        connected: true,
        data: result.data,
        error: null,
        timestamp: result.timestamp,
      });
    } else {
      setHealthStatus({
        loading: false,
        connected: false,
        data: null,
        error: result.error,
        timestamp: result.timestamp,
      });
    }
  }, []);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  return (
    <div className="app-container">
      {/* Top Header */}
      <header className="header-bar">
        <div className="logo-badge">
          <div className="logo-icon">
            <Layers size={22} color="#ffffff" />
          </div>
          <div>
            <div className="logo-text-title">SIH26122</div>
          </div>
        </div>
        <div className="phase-tag">Phase 1 • Foundation</div>
      </header>

      {/* Main Content */}
      <main className="main-content">
        <section className="hero-section">
          <div className="project-id-badge">
            <Activity size={16} />
            <span>SIH26122</span>
          </div>
          <h1 className="hero-title">Intelligent Project Execution Platform</h1>
          <p className="hero-subtitle">Planning-to-Execution Bridge</p>
          <p className="hero-description">
            Intelligent Data Capture & Schedule-Linking Layer for Infrastructure Project Management.
          </p>
        </section>

        {/* Backend Connection Status Section */}
        <section className="status-card" aria-label="Backend Connection Status">
          <div className="card-header">
            <div className="card-title-group">
              <Server size={20} color="#38bdf8" />
              <h2 className="card-title">Backend Connectivity</h2>
            </div>
            
            <div
              className={`status-indicator ${
                healthStatus.loading
                  ? 'checking'
                  : healthStatus.connected
                  ? 'connected'
                  : 'disconnected'
              }`}
            >
              <span className="status-dot"></span>
              <span>
                {healthStatus.loading
                  ? 'Backend Status: Checking...'
                  : healthStatus.connected
                  ? 'Backend Status: Connected'
                  : 'Backend Status: Disconnected'}
              </span>
            </div>
          </div>

          <div className="info-grid">
            <div className="info-item">
              <div className="info-label">Configured API Base URL</div>
              <div className="info-value">{API_BASE_URL}</div>
            </div>
            <div className="info-item">
              <div className="info-label">Health Endpoint</div>
              <div className="info-value">GET /api/health</div>
            </div>
          </div>

          <div className="response-box">
            {healthStatus.loading ? (
              <div>Checking connection to FastAPI backend...</div>
            ) : healthStatus.connected ? (
              <pre>{JSON.stringify(healthStatus.data, null, 2)}</pre>
            ) : (
              <div style={{ color: '#f87171' }}>
                <strong>Connection Error:</strong> {healthStatus.error}
              </div>
            )}
          </div>

          <button
            className="btn-refresh"
            onClick={fetchHealth}
            disabled={healthStatus.loading}
          >
            <RefreshCw
              size={16}
              style={{
                animation: healthStatus.loading ? 'spin 1s linear infinite' : 'none',
              }}
            />
            <span>{healthStatus.loading ? 'Verifying...' : 'Re-check Connection'}</span>
          </button>
        </section>
      </main>

      {/* Footer */}
      <footer className="footer">
        <p>SIH26122 — Smart India Hackathon 2026 • Phase 1 Architecture Foundation</p>
      </footer>
    </div>
  );
}
