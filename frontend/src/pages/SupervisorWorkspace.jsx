import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { testSupervisorRole } from '../services/api';
import Navbar from '../components/Navbar';
import { HardHat, Layers, ShieldCheck, CheckCircle2, AlertTriangle, RefreshCw } from 'lucide-react';

export default function SupervisorWorkspace() {
  const { user, token } = useAuth();
  const [roleTestResult, setRoleTestResult] = useState(null);
  const [isTesting, setIsTesting] = useState(false);

  const handleTestRole = async () => {
    setIsTesting(true);
    setRoleTestResult(null);
    try {
      const result = await testSupervisorRole(token);
      setRoleTestResult(result);
    } catch (err) {
      setRoleTestResult({ status: 500, error: err.message });
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div className="workspace-shell">
      <Navbar workspaceTitle="Supervisor Portal" />

      <main className="workspace-main">
        {/* Workspace Hero */}
        <section className="workspace-hero">
          <div className="workspace-title-row">
            <div className="workspace-avatar-badge supervisor-avatar">
              <HardHat size={28} />
            </div>
            <div>
              <h1 className="workspace-heading">Supervisor Workspace</h1>
              <p className="workspace-welcome-text">
                Welcome, <strong>{user?.full_name}</strong>
              </p>
            </div>
          </div>

          <div className="user-meta-strip">
            <div className="meta-chip">
              <span className="meta-chip-label">Email</span>
              <span className="meta-chip-value">{user?.email}</span>
            </div>
            <div className="meta-chip">
              <span className="meta-chip-label">Role</span>
              <span className="meta-chip-value role-badge-supervisor">{user?.role}</span>
            </div>
            <div className="meta-chip">
              <span className="meta-chip-label">System State</span>
              <span className="meta-chip-value active-status">Active</span>
            </div>
          </div>
        </section>

        {/* Phase Notice Card */}
        <section className="workspace-notice-card">
          <div className="notice-icon-box">
            <Layers size={22} />
          </div>
          <div className="notice-content">
            <h2 className="notice-title">Phase 2 Architecture Foundation</h2>
            <p className="notice-text">
              Project assignments and execution reporting will be available in a later phase.
            </p>
          </div>
        </section>

        {/* Backend Role Security Verification Card */}
        <section className="workspace-panel-card">
          <div className="panel-header">
            <div className="panel-header-title">
              <ShieldCheck size={18} />
              <h3>Backend Role Authorization Verification</h3>
            </div>
            <span className="security-tag">RBAC Protected</span>
          </div>

          <p className="panel-description">
            Test real-time backend authorization for the <code>GET /api/test/supervisor</code> endpoint using your active JWT token.
          </p>

          <button
            type="button"
            className="btn-primary btn-role-test"
            onClick={handleTestRole}
            disabled={isTesting}
          >
            <RefreshCw size={15} className={isTesting ? 'spin-icon' : ''} />
            <span>{isTesting ? 'Verifying RBAC...' : 'Verify Backend Supervisor Access'}</span>
          </button>

          {roleTestResult && (
            <div className="test-result-box">
              <div className="test-result-header">
                <span className="test-status-code">HTTP Status: {roleTestResult.status}</span>
                {roleTestResult.status === 200 ? (
                  <span className="badge-pass">
                    <CheckCircle2 size={13} />
                    <span>200 OK — Authorized</span>
                  </span>
                ) : (
                  <span className="badge-fail">
                    <AlertTriangle size={13} />
                    <span>{roleTestResult.status} Access Denied</span>
                  </span>
                )}
              </div>
              <pre className="test-json-output">
                {JSON.stringify(roleTestResult.data || roleTestResult.error, null, 2)}
              </pre>
            </div>
          )}
        </section>
      </main>

      <footer className="footer">
        <p>© 2026 SIH26122 • Phase 2 Authentication &amp; Role Management</p>
      </footer>
    </div>
  );
}
