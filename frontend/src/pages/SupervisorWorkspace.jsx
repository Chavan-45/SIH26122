import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getProjects } from '../services/api';
import Navbar from '../components/Navbar';
import {
  HardHat,
  Building2,
  Calendar,
  MapPin,
  Tag,
  ArrowRight,
  RefreshCw,
  AlertCircle,
  Briefcase,
  Layers,
  Activity,
  Cpu,
  CheckCircle2,
  TrendingUp,
  Workflow,
} from 'lucide-react';

function formatProjectDate(dateStr) {
  if (!dateStr) return '—';
  try {
    const parts = dateStr.split('-');
    if (parts.length === 3) {
      const year = parseInt(parts[0], 10);
      const month = parseInt(parts[1], 10) - 1;
      const day = parseInt(parts[2], 10);
      const d = new Date(Date.UTC(year, month, day));
      if (!isNaN(d.getTime())) {
        return d.toLocaleDateString('en-GB', {
          day: '2-digit',
          month: 'short',
          year: 'numeric',
          timeZone: 'UTC',
        });
      }
    }
    const d = new Date(dateStr);
    if (!isNaN(d.getTime())) {
      return d.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      });
    }
    return dateStr;
  } catch {
    return dateStr;
  }
}

export default function SupervisorWorkspace() {
  const { user, token } = useAuth();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAssignedProjects = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getProjects(token);
      if (result.success && result.data) {
        setProjects(result.data);
      } else {
        setError(result.error || 'Failed to load assigned projects.');
      }
    } catch (err) {
      setError('An error occurred while fetching your assigned projects.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchAssignedProjects();
  }, [fetchAssignedProjects]);

  // Real data metrics for supervisor
  const metrics = useMemo(() => {
    const total = projects.length;
    const active = projects.filter((p) => p.status === 'ACTIVE').length;
    const disciplines = new Set(
      projects.map((p) => p.assigned_discipline).filter(Boolean)
    ).size;
    return { total, active, disciplines };
  }, [projects]);

  return (
    <div className="workspace-shell">
      <Navbar workspaceTitle="Supervisor Portal" />

      <main className="workspace-main">
        {/* SECTION 1 — PORTFOLIO HERO / HEADER */}
        <section className="portfolio-hero-card">
          <div className="portfolio-hero-left">
            <div className="portfolio-hero-icon supervisor-icon">
              <HardHat size={24} />
            </div>
            <div>
              <h1 className="portfolio-hero-title">Assigned Infrastructure Projects</h1>
              <p className="portfolio-hero-subtitle">
                Access your designated project execution workspaces, log daily progress, and report field actuals.
              </p>
              <div className="portfolio-hero-meta">
                <span>Field Supervisor:</span>
                <strong>{user?.full_name || 'Field Supervisor'}</strong>
              </div>
            </div>
          </div>

          <div className="portfolio-hero-actions">
            <button
              type="button"
              className="btn-icon-secondary"
              onClick={fetchAssignedProjects}
              title="Refresh assigned projects"
              disabled={loading}
            >
              <RefreshCw size={16} className={loading ? 'spin-icon' : ''} />
            </button>
          </div>
        </section>

        {error && (
          <div className="auth-error-banner" role="alert">
            <AlertCircle size={16} className="error-icon" />
            <span>{error}</span>
          </div>
        )}

        {/* SECTION 2 — PORTFOLIO SUMMARY ROW (REAL DATA) */}
        {!loading && (
          <section className="portfolio-kpi-grid">
            <div className="portfolio-kpi-card">
              <div className="portfolio-kpi-header">
                <span className="portfolio-kpi-label">Assigned Projects</span>
                <div className="portfolio-kpi-icon-wrap">
                  <Layers size={15} />
                </div>
              </div>
              <div className="portfolio-kpi-value">{metrics.total}</div>
              <div className="portfolio-kpi-subtext">Active team memberships</div>
            </div>

            <div className="portfolio-kpi-card kpi-active">
              <div className="portfolio-kpi-header">
                <span className="portfolio-kpi-label">Active Projects</span>
                <div className="portfolio-kpi-icon-wrap">
                  <Activity size={15} />
                </div>
              </div>
              <div className="portfolio-kpi-value">{metrics.active}</div>
              <div className="portfolio-kpi-subtext">Currently executing on site</div>
            </div>

            <div className="portfolio-kpi-card kpi-planning">
              <div className="portfolio-kpi-header">
                <span className="portfolio-kpi-label">Assigned Disciplines</span>
                <div className="portfolio-kpi-icon-wrap">
                  <Briefcase size={15} />
                </div>
              </div>
              <div className="portfolio-kpi-value">{metrics.disciplines}</div>
              <div className="portfolio-kpi-subtext">Allocated engineering scopes</div>
            </div>
          </section>
        )}

        {/* SECTION 3 — PROJECTS AREA */}
        <section className="portfolio-projects-section">
          <div className="portfolio-section-head">
            <h2 className="portfolio-section-title">Your Assigned Projects</h2>
            <p className="portfolio-section-desc">
              Select a project to enter the supervisor field workspace.
            </p>
          </div>

          {loading ? (
            <div className="loading-card" style={{ marginTop: '1rem' }}>
              <RefreshCw size={24} className="spin-icon" />
              <span>Loading assigned projects...</span>
            </div>
          ) : projects.length === 0 ? (
            <div className="portfolio-empty-box">
              <div className="portfolio-empty-icon">
                <Building2 size={32} />
              </div>
              <h3 className="portfolio-empty-title">No projects have been assigned to you yet.</h3>
              <p className="portfolio-empty-desc">
                When a Lead Planner assigns your corporate email (<code>{user?.email}</code>) to an infrastructure project team, it will immediately appear in this workspace.
              </p>
            </div>
          ) : (
            <div className="portfolio-projects-grid" style={{ marginTop: '0.85rem' }}>
              {projects.map((proj) => (
                <div key={proj.id} className="portfolio-project-card">
                  <div className="portfolio-card-top">
                    <div className="portfolio-card-code font-mono">
                      <Tag size={12} />
                      <span>{proj.project_code}</span>
                    </div>
                    <div className={`status-pill ${proj.status.toLowerCase()}`}>
                      <span className="status-dot-small"></span>
                      <span>{proj.status.replace('_', ' ')}</span>
                    </div>
                  </div>

                  <div>
                    <h3 className="portfolio-card-title">{proj.name}</h3>

                    {proj.assigned_discipline && (
                      <div className="portfolio-card-discipline" style={{ marginTop: '0.35rem' }}>
                        <Briefcase size={12} />
                        <span>Discipline: <strong>{proj.assigned_discipline}</strong></span>
                      </div>
                    )}

                    {proj.location && (
                      <div className="portfolio-card-location" style={{ marginTop: '0.35rem' }}>
                        <MapPin size={13} />
                        <span>{proj.location}</span>
                      </div>
                    )}
                  </div>

                  <div className="portfolio-card-divider"></div>

                  <div className="portfolio-card-dates font-mono">
                    <div className="portfolio-date-block">
                      <span className="portfolio-date-label">Start</span>
                      <span className="portfolio-date-value">
                        {formatProjectDate(proj.planned_start_date)}
                      </span>
                    </div>
                    <div className="portfolio-date-block">
                      <span className="portfolio-date-label">Finish</span>
                      <span className="portfolio-date-value">
                        {formatProjectDate(proj.planned_end_date)}
                      </span>
                    </div>
                  </div>

                  <div className="portfolio-card-footer">
                    <Link to={`/projects/${proj.id}`} className="btn-portfolio-open">
                      <span>Open Project</span>
                      <ArrowRight size={14} />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* SECTION 4 — WORKSPACE OVERVIEW / KARYASETU WORKFLOW */}
        <section className="portfolio-workflow-card">
          <div className="workflow-header">
            <h2 className="workflow-title">
              <Workflow size={18} style={{ color: 'var(--color-accent)' }} />
              <span>KaryaSetu Workflow</span>
            </h2>
            <p className="workflow-subtitle">
              From baseline planning to verified field execution.
            </p>
          </div>

          <div className="workflow-stages-grid">
            <div className="workflow-stage-item">
              <div className="workflow-stage-top">
                <span className="workflow-stage-num">01</span>
                <Calendar size={16} className="workflow-stage-icon" />
              </div>
              <h4 className="workflow-stage-name">Schedule Baseline</h4>
              <p className="workflow-stage-desc">
                Import structured Primavera / MS Project activities.
              </p>
            </div>

            <div className="workflow-stage-item">
              <div className="workflow-stage-top">
                <span className="workflow-stage-num">02</span>
                <HardHat size={16} className="workflow-stage-icon" />
              </div>
              <h4 className="workflow-stage-name">Field Progress</h4>
              <p className="workflow-stage-desc">
                Capture supervisor updates and DPRs.
              </p>
            </div>

            <div className="workflow-stage-item">
              <div className="workflow-stage-top">
                <span className="workflow-stage-num">03</span>
                <Cpu size={16} className="workflow-stage-icon" />
              </div>
              <h4 className="workflow-stage-name">AI Linking</h4>
              <p className="workflow-stage-desc">
                Map field updates to scheduled activities.
              </p>
            </div>

            <div className="workflow-stage-item">
              <div className="workflow-stage-top">
                <span className="workflow-stage-num">04</span>
                <CheckCircle2 size={16} className="workflow-stage-icon" />
              </div>
              <h4 className="workflow-stage-name">Planner Review</h4>
              <p className="workflow-stage-desc">
                Verify ambiguous or unmatched execution updates.
              </p>
            </div>

            <div className="workflow-stage-item">
              <div className="workflow-stage-top">
                <span className="workflow-stage-num">05</span>
                <TrendingUp size={16} className="workflow-stage-icon" />
              </div>
              <h4 className="workflow-stage-name">Analytics &amp; Schedule Sync</h4>
              <p className="workflow-stage-desc">
                Track actual progress and export schedule-ready actuals.
              </p>
            </div>
          </div>
        </section>
      </main>

      <footer className="footer">
        <p>© 2026 KaryaSetu • Infrastructure Project Intelligence</p>
      </footer>
    </div>
  );
}
