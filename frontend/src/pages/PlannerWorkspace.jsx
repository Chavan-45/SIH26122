import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getProjects } from '../services/api';
import Navbar from '../components/Navbar';
import {
  FolderKanban,
  PlusCircle,
  Building2,
  Calendar,
  MapPin,
  Tag,
  ArrowRight,
  RefreshCw,
  AlertCircle,
  Layers,
} from 'lucide-react';

export default function PlannerWorkspace() {
  const { user, token } = useAuth();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getProjects(token);
      if (result.success && result.data) {
        setProjects(result.data);
      } else {
        setError(result.error || 'Failed to load projects.');
      }
    } catch (err) {
      setError('An error occurred while fetching your projects.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  return (
    <div className="workspace-shell">
      <Navbar workspaceTitle="Planner Portal" />

      <main className="workspace-main">
        {/* Workspace Summary Bar */}
        <section className="workspace-hero-compact">
          <div className="hero-compact-left">
            <div className="workspace-avatar-badge">
              <FolderKanban size={26} />
            </div>
            <div>
              <h1 className="workspace-heading">My Infrastructure Projects</h1>
              <p className="workspace-welcome-text">
                Lead Planner: <strong>{user?.full_name}</strong> • Manage project baselines and supervisor allocations.
              </p>
            </div>
          </div>

          <div className="hero-compact-actions">
            <button
              type="button"
              className="btn-icon-secondary"
              onClick={fetchProjects}
              title="Refresh projects"
              disabled={loading}
            >
              <RefreshCw size={16} className={loading ? 'spin-icon' : ''} />
            </button>

            <Link to="/planner/projects/new" className="btn-primary">
              <PlusCircle size={16} />
              <span>Create Project</span>
            </Link>
          </div>
        </section>

        {error && (
          <div className="auth-error-banner" role="alert">
            <AlertCircle size={16} className="error-icon" />
            <span>{error}</span>
          </div>
        )}

        {/* Project List / Empty State */}
        {loading ? (
          <div className="loading-card">
            <RefreshCw size={24} className="spin-icon" />
            <span>Loading your projects...</span>
          </div>
        ) : projects.length === 0 ? (
          <div className="empty-projects-card">
            <div className="empty-projects-icon">
              <Building2 size={40} />
            </div>
            <h2 className="empty-projects-title">No projects created yet.</h2>
            <p className="empty-projects-desc">
              Create your first infrastructure project baseline to begin managing schedules, locations, and supervisor discipline assignments.
            </p>
            <Link to="/planner/projects/new" className="btn-primary" style={{ marginTop: '0.5rem' }}>
              <PlusCircle size={16} />
              <span>Create Project</span>
            </Link>
          </div>
        ) : (
          <div className="projects-grid">
            {projects.map((proj) => (
              <div key={proj.id} className="project-summary-card">
                <div className="project-card-top">
                  <div className="project-code-tag font-mono">
                    <Tag size={12} />
                    <span>{proj.project_code}</span>
                  </div>
                  <div className={`status-pill ${proj.status.toLowerCase()}`}>
                    <span className="status-dot-small"></span>
                    <span>{proj.status.replace('_', ' ')}</span>
                  </div>
                </div>

                <h2 className="project-card-title">{proj.name}</h2>

                {proj.location && (
                  <div className="project-card-location">
                    <MapPin size={13} />
                    <span>{proj.location}</span>
                  </div>
                )}

                <div className="project-card-dates font-mono">
                  <div className="date-chip">
                    <span className="date-label">Start:</span>
                    <span>{proj.planned_start_date}</span>
                  </div>
                  <div className="date-chip">
                    <span className="date-label">Finish:</span>
                    <span>{proj.planned_end_date}</span>
                  </div>
                </div>

                <div className="project-card-footer">
                  <Link to={`/projects/${proj.id}`} className="btn-open-project">
                    <span>Open Project</span>
                    <ArrowRight size={14} />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      <footer className="footer">
        <p>© 2026 SIH26122 • Phase 3 Project Management &amp; Access Controls</p>
      </footer>
    </div>
  );
}
