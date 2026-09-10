import React, { useState, useEffect, useCallback, useMemo } from 'react';
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
  Activity,
  HardHat,
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

  // Derive real portfolio metrics without modifying backend
  const metrics = useMemo(() => {
    const total = projects.length;
    const active = projects.filter((p) => p.status === 'ACTIVE').length;
    const planning = projects.filter((p) => p.status === 'PLANNING').length;
    return { total, active, planning };
  }, [projects]);

  return (
    <div className="workspace-shell">
      <Navbar workspaceTitle="Planner Portal" />

      <main className="workspace-main">
        {/* SECTION 1 — PORTFOLIO HERO / HEADER */}
        <section className="portfolio-hero-card">
          <div className="portfolio-hero-left">
            <div className="portfolio-hero-icon">
              <FolderKanban size={24} />
            </div>
            <div>
              <h1 className="portfolio-hero-title">My Infrastructure Projects</h1>
              <p className="portfolio-hero-subtitle">
                Manage project baselines, field execution and supervisor allocations from one workspace.
              </p>
              <div className="portfolio-hero-meta">
                <span>Lead Planner:</span>
                <strong>{user?.full_name || 'Lead Planner'}</strong>
              </div>
            </div>
          </div>

          <div className="portfolio-hero-actions">
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
              <span>+ Create Project</span>
            </Link>
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
                <span className="portfolio-kpi-label">Total Projects</span>
                <div className="portfolio-kpi-icon-wrap">
                  <Layers size={15} />
                </div>
              </div>
              <div className="portfolio-kpi-value">{metrics.total}</div>
              <div className="portfolio-kpi-subtext">Configured project workspaces</div>
            </div>

            <div className="portfolio-kpi-card kpi-active">
              <div className="portfolio-kpi-header">
                <span className="portfolio-kpi-label">Active Projects</span>
                <div className="portfolio-kpi-icon-wrap">
                  <Activity size={15} />
                </div>
              </div>
              <div className="portfolio-kpi-value">{metrics.active}</div>
              <div className="portfolio-kpi-subtext">Currently in active field execution</div>
            </div>

            <div className="portfolio-kpi-card kpi-planning">
              <div className="portfolio-kpi-header">
                <span className="portfolio-kpi-label">Planning &amp; Setup</span>
                <div className="portfolio-kpi-icon-wrap">
                  <Calendar size={15} />
                </div>
              </div>
              <div className="portfolio-kpi-value">{metrics.planning}</div>
              <div className="portfolio-kpi-subtext">Baseline schedule staging</div>
            </div>
          </section>
        )}

        {/* SECTION 3 — PROJECTS AREA */}
        <section className="portfolio-projects-section">
          <div className="portfolio-section-head">
            <h2 className="portfolio-section-title">Your Projects</h2>
            <p className="portfolio-section-desc">
              Select a project to open its execution workspace.
            </p>
          </div>

          {loading ? (
            <div className="loading-card" style={{ marginTop: '1rem' }}>
              <RefreshCw size={24} className="spin-icon" />
              <span>Loading your projects...</span>
            </div>
          ) : projects.length === 0 ? (
            <div className="portfolio-empty-box">
              <div className="portfolio-empty-icon">
                <Building2 size={32} />
              </div>
              <h3 className="portfolio-empty-title">No infrastructure projects yet.</h3>
              <p className="portfolio-empty-desc">
                Create your first project to begin importing a schedule and tracking field execution.
              </p>
              <Link to="/planner/projects/new" className="btn-primary" style={{ marginTop: '0.25rem' }}>
                <PlusCircle size={16} />
                <span>+ Create Project</span>
              </Link>
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

                    {proj.location && (
                      <div className="portfolio-card-location">
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
