import React, { useState, useEffect, useCallback } from 'react';
import { getProjectDashboard } from '../services/api';
import {
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Calendar,
  Layers,
  RefreshCw,
  Info,
  Building2,
  FileSpreadsheet,
  Activity,
  ArrowRight,
  Shield,
  Briefcase,
  User,
  Check,
  AlertCircle,
  Play,
  Pause,
  RotateCcw,
} from 'lucide-react';

export default function DashboardTab({
  projectId,
  token,
  isPlannerOwner,
  assignedDiscipline,
  onSelectActivity,
  onNavigateToSchedule,
}) {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState('');
  const [activeDisciplineFilter, setActiveDisciplineFilter] = useState('ALL');

  const fetchDashboard = useCallback(async (isSilent = false) => {
    if (!isSilent) {
      setRefreshing(true);
    }
    setError(null);

    try {
      const res = await getProjectDashboard(token, projectId);
      if (res.success && res.data) {
        setDashboardData(res.data);
        setLastUpdated(new Date().toLocaleTimeString());
      } else {
        if (!isSilent) {
          setError(res.error || 'Failed to load dashboard data.');
        }
      }
    } catch (err) {
      if (!isSilent) {
        setError('Network error while loading dashboard metrics.');
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token, projectId]);

  // Initial load
  useEffect(() => {
    fetchDashboard(false);
  }, [fetchDashboard]);

  // 30-second silent background polling while dashboard tab is mounted
  useEffect(() => {
    const timer = setInterval(() => {
      fetchDashboard(true);
    }, 30000);

    return () => clearInterval(timer);
  }, [fetchDashboard]);

  if (loading && !dashboardData) {
    return (
      <div className="workspace-panel-card" style={{ padding: '3rem', textAlign: 'center' }}>
        <RefreshCw size={28} className="spin-icon" style={{ color: 'var(--color-primary)', marginBottom: '1rem' }} />
        <p style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>Loading Real Project Control Dashboard...</p>
        <span style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
          Computing database-derived schedule health and execution variance...
        </span>
      </div>
    );
  }

  if (error && !dashboardData) {
    return (
      <div className="error-card">
        <AlertCircle size={32} className="error-icon" />
        <h2>Dashboard Calculation Failure</h2>
        <p>{error}</p>
        <button type="button" className="btn-primary" onClick={() => fetchDashboard(false)} style={{ marginTop: '1rem' }}>
          <RefreshCw size={14} /> Retry Loading Dashboard
        </button>
      </div>
    );
  }

  if (!dashboardData) return null;

  const {
    project,
    summary,
    schedule_health,
    discipline_progress,
    today_work,
    overdue_activities,
    upcoming_deadlines,
    recent_updates,
    baseline_actual,
    supervisor_summary,
  } = dashboardData;

  const hasNoSchedule = summary.total_activities === 0;

  // Filter tables if Planner selects a discipline filter tab
  const filteredTodayWork =
    activeDisciplineFilter === 'ALL'
      ? today_work
      : today_work.filter((a) => a.discipline.toUpperCase() === activeDisciplineFilter.toUpperCase());

  const filteredOverdue =
    activeDisciplineFilter === 'ALL'
      ? overdue_activities
      : overdue_activities.filter((a) => a.discipline.toUpperCase() === activeDisciplineFilter.toUpperCase());

  const filteredUpcoming =
    activeDisciplineFilter === 'ALL'
      ? upcoming_deadlines
      : upcoming_deadlines.filter((a) => a.discipline.toUpperCase() === activeDisciplineFilter.toUpperCase());

  return (
    <div className="dashboard-tab-content" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* 1. DASHBOARD CONTROL BAR */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
          backgroundColor: 'var(--color-surface)',
          padding: '0.85rem 1.25rem',
          borderRadius: '8px',
          border: '1px solid var(--color-border)',
          boxShadow: 'var(--shadow-sm)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div
            style={{
              padding: '0.4rem 0.6rem',
              borderRadius: '6px',
              backgroundColor: 'var(--color-primary-light)',
              color: 'var(--color-primary)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontWeight: 600,
              fontSize: '0.85rem',
            }}
          >
            <Activity size={16} />
            <span>PROJECT CONTROL DASHBOARD</span>
          </div>

          <div
            style={{
              fontSize: '0.75rem',
              color: 'var(--color-text-secondary)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
            }}
            title="Physical progress is activity-count weighted across all scheduled items"
          >
            <Info size={14} style={{ color: 'var(--color-accent)' }} />
            <span>Activity-weighted physical progress</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {lastUpdated && (
            <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>
              Last updated: {lastUpdated}
            </span>
          )}
          <button
            type="button"
            className="btn-secondary btn-sm"
            onClick={() => fetchDashboard(false)}
            disabled={refreshing}
            style={{ gap: '0.4rem' }}
          >
            <RefreshCw size={14} className={refreshing ? 'spin-icon' : ''} />
            <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>
      </div>

      {/* EMPTY SCHEDULE STATE */}
      {hasNoSchedule && (
        <div className="workspace-panel-card" style={{ padding: '3rem', textAlign: 'center' }}>
          <FileSpreadsheet size={44} style={{ color: 'var(--color-text-muted)', marginBottom: '1rem' }} />
          <h3 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>
            No Baseline Schedule Imported
          </h3>
          <p style={{ maxWidth: '540px', margin: '0.5rem auto 1.5rem', color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>
            {isPlannerOwner
              ? 'Import a Primavera P6 or MS Project CSV/XLSX schedule baseline to populate real-time project analytics, discipline progress, and overdue tracking.'
              : 'The project planner has not yet uploaded the baseline schedule. Dashboard metrics will activate once schedule activities are imported.'}
          </p>
          {isPlannerOwner && (
            <button type="button" className="btn-primary" onClick={onNavigateToSchedule}>
              Go to Schedule Baseline Import →
            </button>
          )}
        </div>
      )}

      {!hasNoSchedule && (
        <>
          {/* 2. SUPERVISOR MY DISCIPLINE HERO SECTION */}
          {supervisor_summary && (
            <section
              style={{
                backgroundColor: 'var(--color-primary)',
                color: '#FFFFFF',
                borderRadius: '10px',
                padding: '1.25rem 1.5rem',
                boxShadow: 'var(--shadow-card)',
                display: 'flex',
                flexDirection: 'column',
                gap: '1rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <div
                    style={{
                      width: '40px',
                      height: '40px',
                      borderRadius: '8px',
                      backgroundColor: 'rgba(255, 255, 255, 0.15)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <Briefcase size={20} style={{ color: 'var(--color-accent)' }} />
                  </div>
                  <div>
                    <span style={{ fontSize: '0.75rem', letterSpacing: '0.05em', textTransform: 'uppercase', opacity: 0.8 }}>
                      YOUR ASSIGNED OPERATIONAL DISCIPLINE
                    </span>
                    <h2 style={{ fontSize: '1.4rem', fontWeight: 700, margin: 0, color: '#FFFFFF' }}>
                      MY DISCIPLINE — {supervisor_summary.assigned_discipline}
                    </h2>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
                  <div style={{ textAlign: 'right' }}>
                    <span style={{ fontSize: '0.75rem', opacity: 0.8, display: 'block' }}>Discipline Progress</span>
                    <span style={{ fontSize: '1.6rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: 'var(--color-accent)' }}>
                      {supervisor_summary.overall_progress}%
                    </span>
                  </div>
                </div>
              </div>

              {/* Supervisor discipline mini stat pills */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                  gap: '0.75rem',
                  paddingTop: '0.75rem',
                  borderTop: '1px solid rgba(255, 255, 255, 0.15)',
                }}
              >
                <div style={{ backgroundColor: 'rgba(255, 255, 255, 0.08)', padding: '0.6rem 0.85rem', borderRadius: '6px' }}>
                  <span style={{ fontSize: '0.72rem', opacity: 0.8, display: 'block' }}>Total Activities</span>
                  <span style={{ fontSize: '1.15rem', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                    {supervisor_summary.total_activities}
                  </span>
                </div>
                <div style={{ backgroundColor: 'rgba(255, 255, 255, 0.08)', padding: '0.6rem 0.85rem', borderRadius: '6px' }}>
                  <span style={{ fontSize: '0.72rem', opacity: 0.8, display: 'block' }}>Completed</span>
                  <span style={{ fontSize: '1.15rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#86EFAC' }}>
                    {supervisor_summary.completed}
                  </span>
                </div>
                <div style={{ backgroundColor: 'rgba(255, 255, 255, 0.08)', padding: '0.6rem 0.85rem', borderRadius: '6px' }}>
                  <span style={{ fontSize: '0.72rem', opacity: 0.8, display: 'block' }}>In Progress</span>
                  <span style={{ fontSize: '1.15rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#93C5FD' }}>
                    {supervisor_summary.in_progress}
                  </span>
                </div>
                <div style={{ backgroundColor: 'rgba(255, 255, 255, 0.08)', padding: '0.6rem 0.85rem', borderRadius: '6px' }}>
                  <span style={{ fontSize: '0.72rem', opacity: 0.8, display: 'block' }}>Currently Overdue</span>
                  <span
                    style={{
                      fontSize: '1.15rem',
                      fontWeight: 700,
                      fontFamily: 'var(--font-mono)',
                      color: supervisor_summary.overdue > 0 ? '#FCA5A5' : '#FFFFFF',
                    }}
                  >
                    {supervisor_summary.overdue}
                  </span>
                </div>
              </div>
            </section>
          )}

          {/* 3. KEY METRICS GRID (6 Cards) */}
          <section className="kpi-grid-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
            {/* Overall Progress */}
            <div className="kpi-card" style={{ borderLeft: '4px solid var(--color-accent)' }}>
              <span className="kpi-label" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <TrendingUp size={14} style={{ color: 'var(--color-accent)' }} />
                Overall Progress
              </span>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginTop: '0.25rem' }}>
                <span className="kpi-value font-mono" style={{ fontSize: '1.8rem', color: 'var(--color-text-primary)' }}>
                  {summary.overall_progress}%
                </span>
              </div>
              <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginTop: '0.25rem', display: 'block' }}>
                Activity-weighted
              </span>
            </div>

            {/* Total Activities */}
            <div className="kpi-card" style={{ borderLeft: '4px solid var(--color-primary)' }}>
              <span className="kpi-label">Total Activities</span>
              <span className="kpi-value font-mono" style={{ fontSize: '1.8rem', color: 'var(--color-primary)' }}>
                {summary.total_activities}
              </span>
              <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginTop: '0.25rem', display: 'block' }}>
                Baseline activities
              </span>
            </div>

            {/* Completed */}
            <div className="kpi-card" style={{ borderLeft: '4px solid var(--color-success)' }}>
              <span className="kpi-label">Completed</span>
              <span className="kpi-value font-mono" style={{ fontSize: '1.8rem', color: 'var(--color-success)' }}>
                {summary.completed}
              </span>
              <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginTop: '0.25rem', display: 'block' }}>
                {((summary.completed / summary.total_activities) * 100).toFixed(1)}% finished
              </span>
            </div>

            {/* In Progress */}
            <div className="kpi-card" style={{ borderLeft: '4px solid #2563EB' }}>
              <span className="kpi-label">In Progress</span>
              <span className="kpi-value font-mono" style={{ fontSize: '1.8rem', color: '#2563EB' }}>
                {summary.in_progress}
              </span>
              <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginTop: '0.25rem', display: 'block' }}>
                Active execution
              </span>
            </div>

            {/* Overdue */}
            <div className="kpi-card" style={{ borderLeft: `4px solid ${summary.overdue > 0 ? 'var(--color-danger)' : 'var(--color-border)'}` }}>
              <span className="kpi-label" style={{ color: summary.overdue > 0 ? 'var(--color-danger)' : 'inherit' }}>
                Overdue Work
              </span>
              <span className="kpi-value font-mono" style={{ fontSize: '1.8rem', color: summary.overdue > 0 ? 'var(--color-danger)' : 'var(--color-text-primary)' }}>
                {summary.overdue}
              </span>
              <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginTop: '0.25rem', display: 'block' }}>
                Passed planned finish
              </span>
            </div>

            {/* Planned Finish & Days Remaining */}
            <div className="kpi-card" style={{ borderLeft: '4px solid var(--color-warning)' }}>
              <span className="kpi-label">Planned Project Finish</span>
              <span className="kpi-value font-mono" style={{ fontSize: '1.15rem', color: 'var(--color-text-primary)' }}>
                {project.planned_end_date || 'N/A'}
              </span>
              <span
                style={{
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  marginTop: '0.35rem',
                  display: 'inline-block',
                  padding: '0.15rem 0.45rem',
                  borderRadius: '4px',
                  backgroundColor: project.days_until_planned_finish < 0 ? 'var(--color-danger-bg)' : 'var(--color-warning-bg)',
                  color: project.days_until_planned_finish < 0 ? 'var(--color-danger-text)' : 'var(--color-warning-text)',
                }}
              >
                {project.deadline_label}
              </span>
            </div>
          </section>

          {/* 4. STATUS DISTRIBUTION & BASELINE VS ACTUAL GRID */}
          <div className="project-grid-2">
            {/* Status Distribution */}
            <section className="workspace-panel-card">
              <div className="panel-header">
                <div className="panel-header-title">
                  <Layers size={18} />
                  <h3>Activity Status Distribution</h3>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', marginTop: '0.5rem' }}>
                {/* Visual Stacked Bar */}
                <div
                  style={{
                    height: '24px',
                    borderRadius: '6px',
                    backgroundColor: 'var(--color-surface-subtle)',
                    display: 'flex',
                    overflow: 'hidden',
                    border: '1px solid var(--color-border)',
                  }}
                >
                  {summary.completed > 0 && (
                    <div
                      style={{
                        width: `${(summary.completed / summary.total_activities) * 100}%`,
                        backgroundColor: 'var(--color-success)',
                      }}
                      title={`Completed: ${summary.completed}`}
                    />
                  )}
                  {summary.in_progress > 0 && (
                    <div
                      style={{
                        width: `${(summary.in_progress / summary.total_activities) * 100}%`,
                        backgroundColor: '#2563EB',
                      }}
                      title={`In Progress: ${summary.in_progress}`}
                    />
                  )}
                  {summary.on_hold > 0 && (
                    <div
                      style={{
                        width: `${(summary.on_hold / summary.total_activities) * 100}%`,
                        backgroundColor: 'var(--color-warning)',
                      }}
                      title={`On Hold: ${summary.on_hold}`}
                    />
                  )}
                  {summary.not_started > 0 && (
                    <div
                      style={{
                        width: `${(summary.not_started / summary.total_activities) * 100}%`,
                        backgroundColor: 'var(--color-border-strong)',
                      }}
                      title={`Not Started: ${summary.not_started}`}
                    />
                  )}
                </div>

                {/* Status Legend Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.75rem' }}>
                  <div
                    style={{
                      padding: '0.65rem',
                      borderRadius: '6px',
                      backgroundColor: 'var(--color-bg)',
                      border: '1px solid var(--color-border)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: 'var(--color-success)' }} />
                      <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>Completed</span>
                    </div>
                    <span className="font-mono" style={{ fontWeight: 700 }}>{summary.completed}</span>
                  </div>

                  <div
                    style={{
                      padding: '0.65rem',
                      borderRadius: '6px',
                      backgroundColor: 'var(--color-bg)',
                      border: '1px solid var(--color-border)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#2563EB' }} />
                      <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>In Progress</span>
                    </div>
                    <span className="font-mono" style={{ fontWeight: 700 }}>{summary.in_progress}</span>
                  </div>

                  <div
                    style={{
                      padding: '0.65rem',
                      borderRadius: '6px',
                      backgroundColor: 'var(--color-bg)',
                      border: '1px solid var(--color-border)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: 'var(--color-warning)' }} />
                      <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>On Hold</span>
                    </div>
                    <span className="font-mono" style={{ fontWeight: 700 }}>{summary.on_hold}</span>
                  </div>

                  <div
                    style={{
                      padding: '0.65rem',
                      borderRadius: '6px',
                      backgroundColor: 'var(--color-bg)',
                      border: '1px solid var(--color-border)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: 'var(--color-border-strong)' }} />
                      <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>Not Started</span>
                    </div>
                    <span className="font-mono" style={{ fontWeight: 700 }}>{summary.not_started}</span>
                  </div>
                </div>
              </div>
            </section>

            {/* Baseline vs Actual Adherence */}
            <section className="workspace-panel-card">
              <div className="panel-header">
                <div className="panel-header-title">
                  <TrendingUp size={18} />
                  <h3>Baseline vs Actual Execution Adherence</h3>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', marginTop: '0.5rem' }}>
                <p style={{ fontSize: '0.82rem', color: 'var(--color-text-secondary)', margin: 0 }}>
                  Schedule adherence comparison as of today.
                </p>

                {/* Started Comparison */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.35rem' }}>
                    <span style={{ fontWeight: 600 }}>Activities Scheduled to Have Started</span>
                    <span className="font-mono">
                      {baseline_actual.actually_started} / {baseline_actual.scheduled_to_have_started} started
                    </span>
                  </div>
                  <div
                    style={{
                      height: '16px',
                      borderRadius: '4px',
                      backgroundColor: 'var(--color-surface-subtle)',
                      overflow: 'hidden',
                      display: 'flex',
                      position: 'relative',
                    }}
                  >
                    <div
                      style={{
                        width: `${
                          baseline_actual.scheduled_to_have_started > 0
                            ? Math.min(100, (baseline_actual.actually_started / baseline_actual.scheduled_to_have_started) * 100)
                            : 0
                        }%`,
                        backgroundColor:
                          baseline_actual.actually_started >= baseline_actual.scheduled_to_have_started
                            ? 'var(--color-success)'
                            : 'var(--color-accent)',
                        borderRadius: '4px',
                        height: '100%',
                      }}
                    />
                  </div>
                </div>

                {/* Finished Comparison */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.35rem' }}>
                    <span style={{ fontWeight: 600 }}>Activities Scheduled to Have Finished</span>
                    <span className="font-mono">
                      {baseline_actual.actually_completed} / {baseline_actual.scheduled_to_have_finished} finished
                    </span>
                  </div>
                  <div
                    style={{
                      height: '16px',
                      borderRadius: '4px',
                      backgroundColor: 'var(--color-surface-subtle)',
                      overflow: 'hidden',
                      display: 'flex',
                      position: 'relative',
                    }}
                  >
                    <div
                      style={{
                        width: `${
                          baseline_actual.scheduled_to_have_finished > 0
                            ? Math.min(100, (baseline_actual.actually_completed / baseline_actual.scheduled_to_have_finished) * 100)
                            : 0
                        }%`,
                        backgroundColor:
                          baseline_actual.actually_completed >= baseline_actual.scheduled_to_have_finished
                            ? 'var(--color-success)'
                            : 'var(--color-danger)',
                        borderRadius: '4px',
                        height: '100%',
                      }}
                    />
                  </div>
                </div>

                {/* Additional Schedule Health Details */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(2, 1fr)',
                    gap: '0.75rem',
                    paddingTop: '0.5rem',
                    borderTop: '1px solid var(--color-border)',
                    fontSize: '0.8rem',
                  }}
                >
                  <div>
                    <span style={{ color: 'var(--color-text-secondary)' }}>Completed Late:</span>{' '}
                    <strong className="font-mono" style={{ color: schedule_health.completed_late_count > 0 ? 'var(--color-danger)' : 'inherit' }}>
                      {schedule_health.completed_late_count}
                    </strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--color-text-secondary)' }}>Completed On Time/Early:</span>{' '}
                    <strong className="font-mono" style={{ color: 'var(--color-success)' }}>
                      {schedule_health.completed_on_time_or_early_count}
                    </strong>
                  </div>
                </div>
              </div>
            </section>
          </div>

          {/* 5. DISCIPLINE PROGRESS SECTION */}
          <section className="workspace-panel-card">
            <div className="panel-header">
              <div className="panel-header-title">
                <Briefcase size={18} />
                <h3>Discipline Progress Breakdown</h3>
              </div>
              {/* Optional discipline quick filter tabs */}
              <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className={`btn-secondary btn-sm ${activeDisciplineFilter === 'ALL' ? 'active-filter' : ''}`}
                  onClick={() => setActiveDisciplineFilter('ALL')}
                  style={{
                    backgroundColor: activeDisciplineFilter === 'ALL' ? 'var(--color-primary)' : 'inherit',
                    color: activeDisciplineFilter === 'ALL' ? '#FFFFFF' : 'inherit',
                  }}
                >
                  All Disciplines
                </button>
                {discipline_progress.map((d) => (
                  <button
                    key={d.discipline}
                    type="button"
                    className={`btn-secondary btn-sm ${activeDisciplineFilter === d.discipline ? 'active-filter' : ''}`}
                    onClick={() => setActiveDisciplineFilter(d.discipline)}
                    style={{
                      backgroundColor: activeDisciplineFilter === d.discipline ? 'var(--color-primary)' : 'inherit',
                      color: activeDisciplineFilter === d.discipline ? '#FFFFFF' : 'inherit',
                    }}
                  >
                    {d.discipline} ({d.total_activities})
                  </button>
                ))}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem', marginTop: '0.75rem' }}>
              {discipline_progress.map((disc) => {
                const isUserAssigned = assignedDiscipline && disc.discipline.toUpperCase() === assignedDiscipline.toUpperCase();

                return (
                  <div
                    key={disc.discipline}
                    style={{
                      padding: '1rem',
                      borderRadius: '8px',
                      backgroundColor: isUserAssigned ? 'var(--color-accent-light)' : 'var(--color-bg)',
                      border: isUserAssigned ? '2px solid var(--color-accent)' : '1px solid var(--color-border)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.65rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <span style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--color-text-primary)' }}>
                          {disc.discipline}
                        </span>
                        {isUserAssigned && (
                          <span
                            style={{
                              fontSize: '0.65rem',
                              fontWeight: 700,
                              textTransform: 'uppercase',
                              backgroundColor: 'var(--color-accent)',
                              color: '#FFFFFF',
                              padding: '0.1rem 0.4rem',
                              borderRadius: '4px',
                            }}
                          >
                            My Discipline
                          </span>
                        )}
                      </div>
                      <span className="font-mono" style={{ fontWeight: 800, fontSize: '1.1rem', color: 'var(--color-primary)' }}>
                        {disc.overall_progress}%
                      </span>
                    </div>

                    {/* Progress Bar */}
                    <div
                      style={{
                        height: '8px',
                        borderRadius: '4px',
                        backgroundColor: 'var(--color-border)',
                        overflow: 'hidden',
                      }}
                    >
                      <div
                        style={{
                          width: `${disc.overall_progress}%`,
                          backgroundColor: 'var(--color-accent)',
                          height: '100%',
                          borderRadius: '4px',
                        }}
                      />
                    </div>

                    {/* Activity Status Count Summary */}
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        fontSize: '0.75rem',
                        color: 'var(--color-text-secondary)',
                      }}
                    >
                      <span>Tot: <strong>{disc.total_activities}</strong></span>
                      <span>Comp: <strong style={{ color: 'var(--color-success)' }}>{disc.completed}</strong></span>
                      <span>InProg: <strong style={{ color: '#2563EB' }}>{disc.in_progress}</strong></span>
                      {disc.overdue > 0 && (
                        <span>Overdue: <strong style={{ color: 'var(--color-danger)' }}>{disc.overdue}</strong></span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* 6. OVERDUE ACTIVITIES SECTION (High Priority Header) */}
          <section className="workspace-panel-card" style={{ borderTop: filteredOverdue.length > 0 ? '4px solid var(--color-danger)' : '1px solid var(--color-border)' }}>
            <div className="panel-header">
              <div className="panel-header-title">
                <AlertTriangle size={18} style={{ color: filteredOverdue.length > 0 ? 'var(--color-danger)' : 'var(--color-text-secondary)' }} />
                <h3>Overdue Carryover Activities</h3>
                <span className="level-badge font-mono" style={{ backgroundColor: filteredOverdue.length > 0 ? 'var(--color-danger-bg)' : 'var(--color-surface-subtle)', color: filteredOverdue.length > 0 ? 'var(--color-danger-text)' : 'inherit' }}>
                  {filteredOverdue.length} Overdue
                </span>
              </div>
            </div>

            {filteredOverdue.length === 0 ? (
              <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>
                <CheckCircle2 size={24} style={{ color: 'var(--color-success)', marginBottom: '0.5rem' }} />
                <p style={{ margin: 0, fontWeight: 500 }}>No activities are currently overdue.</p>
              </div>
            ) : (
              <div className="table-responsive">
                <table className="schedule-table">
                  <thead>
                    <tr>
                      <th>Activity Code</th>
                      <th>Activity Name</th>
                      <th>Discipline</th>
                      <th>Planned Finish</th>
                      <th>Overdue Days</th>
                      <th>Progress</th>
                      <th>Status</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredOverdue.map((act) => (
                      <tr
                        key={act.activity_id}
                        style={{ cursor: 'pointer' }}
                        onClick={() => onSelectActivity && onSelectActivity(act.activity_id)}
                      >
                        <td className="font-mono" style={{ fontWeight: 600 }}>{act.activity_code}</td>
                        <td>{act.activity_name}</td>
                        <td>
                          <span className="discipline-tag">{act.discipline}</span>
                        </td>
                        <td className="font-mono">{act.planned_finish}</td>
                        <td>
                          <span
                            className="font-mono"
                            style={{
                              fontWeight: 700,
                              color: 'var(--color-danger)',
                              backgroundColor: 'var(--color-danger-bg)',
                              padding: '0.15rem 0.45rem',
                              borderRadius: '4px',
                            }}
                          >
                            +{act.overdue_days} days
                          </span>
                        </td>
                        <td className="font-mono">{act.progress_percentage}%</td>
                        <td>
                          <span className={`status-pill ${act.execution_status.toLowerCase()}`}>
                            <span className="status-dot-small" />
                            <span>{act.execution_status.replace('_', ' ')}</span>
                          </span>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="btn-secondary btn-sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              onSelectActivity && onSelectActivity(act.activity_id);
                            }}
                          >
                            View Detail
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* 7. TODAY'S SCHEDULED WORK & UPCOMING DEADLINES (2-Column Grid) */}
          <div className="project-grid-2">
            {/* Today's Scheduled Work */}
            <section className="workspace-panel-card">
              <div className="panel-header">
                <div className="panel-header-title">
                  <Clock size={18} style={{ color: 'var(--color-primary)' }} />
                  <h3>Scheduled Today ({filteredTodayWork.length})</h3>
                </div>
              </div>

              {filteredTodayWork.length === 0 ? (
                <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--color-text-secondary)', fontSize: '0.88rem' }}>
                  <p style={{ margin: 0 }}>No activities are scheduled for execution today.</p>
                </div>
              ) : (
                <div className="table-responsive">
                  <table className="schedule-table" style={{ fontSize: '0.83rem' }}>
                    <thead>
                      <tr>
                        <th>Code</th>
                        <th>Name</th>
                        <th>Disc</th>
                        <th>Finish</th>
                        <th>Prog</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredTodayWork.map((act) => (
                        <tr
                          key={act.activity_id}
                          style={{ cursor: 'pointer' }}
                          onClick={() => onSelectActivity && onSelectActivity(act.activity_id)}
                        >
                          <td className="font-mono" style={{ fontWeight: 600 }}>{act.activity_code}</td>
                          <td>{act.activity_name}</td>
                          <td>
                            <span className="discipline-tag" style={{ fontSize: '0.7rem' }}>{act.discipline}</span>
                          </td>
                          <td className="font-mono">{act.planned_finish}</td>
                          <td className="font-mono">{act.progress_percentage}%</td>
                          <td>
                            <button
                              type="button"
                              className="btn-secondary btn-sm"
                              style={{ padding: '0.2rem 0.4rem', fontSize: '0.75rem' }}
                              onClick={(e) => {
                                e.stopPropagation();
                                onSelectActivity && onSelectActivity(act.activity_id);
                              }}
                            >
                              View
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* Upcoming Deadlines (Next 7 Days) */}
            <section className="workspace-panel-card">
              <div className="panel-header">
                <div className="panel-header-title">
                  <Calendar size={18} style={{ color: 'var(--color-accent)' }} />
                  <h3>Upcoming Deadlines — 7 Days ({filteredUpcoming.length})</h3>
                </div>
              </div>

              {filteredUpcoming.length === 0 ? (
                <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--color-text-secondary)', fontSize: '0.88rem' }}>
                  <p style={{ margin: 0 }}>No activity deadlines within the next 7 days.</p>
                </div>
              ) : (
                <div className="table-responsive">
                  <table className="schedule-table" style={{ fontSize: '0.83rem' }}>
                    <thead>
                      <tr>
                        <th>Code</th>
                        <th>Name</th>
                        <th>Disc</th>
                        <th>Planned Finish</th>
                        <th>Due</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredUpcoming.map((act) => (
                        <tr
                          key={act.activity_id}
                          style={{ cursor: 'pointer' }}
                          onClick={() => onSelectActivity && onSelectActivity(act.activity_id)}
                        >
                          <td className="font-mono" style={{ fontWeight: 600 }}>{act.activity_code}</td>
                          <td>{act.activity_name}</td>
                          <td>
                            <span className="discipline-tag" style={{ fontSize: '0.7rem' }}>{act.discipline}</span>
                          </td>
                          <td className="font-mono">{act.planned_finish}</td>
                          <td>
                            <span
                              className="font-mono"
                              style={{
                                fontWeight: 600,
                                color: 'var(--color-warning-text)',
                                backgroundColor: 'var(--color-warning-bg)',
                                padding: '0.1rem 0.35rem',
                                borderRadius: '4px',
                                fontSize: '0.75rem',
                              }}
                            >
                              {act.days_until_finish === 0 ? 'Today' : `In ${act.days_until_finish}d`}
                            </span>
                          </td>
                          <td>
                            <button
                              type="button"
                              className="btn-secondary btn-sm"
                              style={{ padding: '0.2rem 0.4rem', fontSize: '0.75rem' }}
                              onClick={(e) => {
                                e.stopPropagation();
                                onSelectActivity && onSelectActivity(act.activity_id);
                              }}
                            >
                              View
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>

          {/* 8. RECENT SITE UPDATES FEED */}
          <section className="workspace-panel-card">
            <div className="panel-header">
              <div className="panel-header-title">
                <Activity size={18} style={{ color: 'var(--color-primary)' }} />
                <h3>Recent Site Progress Updates Feed</h3>
              </div>
            </div>

            {recent_updates.length === 0 ? (
              <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--color-text-secondary)', fontSize: '0.88rem' }}>
                <p style={{ margin: 0 }}>No progress updates recorded yet.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '0.5rem' }}>
                {recent_updates.map((upd) => (
                  <div
                    key={upd.id}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '0.85rem',
                      padding: '0.85rem 1rem',
                      borderRadius: '8px',
                      backgroundColor: 'var(--color-bg)',
                      border: '1px solid var(--color-border)',
                    }}
                  >
                    <div
                      style={{
                        padding: '0.4rem',
                        borderRadius: '6px',
                        backgroundColor: 'var(--color-surface-subtle)',
                        color: 'var(--color-primary)',
                        marginTop: '0.1rem',
                      }}
                    >
                      <CheckCircle2 size={16} style={{ color: 'var(--color-success)' }} />
                    </div>

                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span className="font-mono" style={{ fontWeight: 700, fontSize: '0.9rem' }}>
                            {upd.activity_code}
                          </span>
                          <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--color-text-primary)' }}>
                            — {upd.activity_name}
                          </span>
                          <span className="discipline-tag" style={{ fontSize: '0.7rem' }}>
                            {upd.discipline}
                          </span>
                        </div>

                        <span className="font-mono" style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                          {new Date(upd.created_at).toLocaleString()}
                        </span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontSize: '0.82rem', color: 'var(--color-text-secondary)', marginTop: '0.15rem' }}>
                        <span>
                          Action: <strong>{upd.update_type}</strong>
                        </span>
                        <span>
                          Progress: <strong className="font-mono">{upd.progress_percentage}%</strong>
                        </span>
                        <span>
                          Reporter: <strong>{upd.reporter_name}</strong>
                        </span>
                        <span>
                          Source: <span className="font-mono">{upd.source_type}</span>
                        </span>
                      </div>

                      {upd.remarks && (
                        <p
                          style={{
                            fontSize: '0.8rem',
                            color: 'var(--color-text-primary)',
                            backgroundColor: 'var(--color-surface)',
                            padding: '0.4rem 0.65rem',
                            borderRadius: '4px',
                            border: '1px solid var(--color-border-subtle)',
                            margin: '0.35rem 0 0',
                          }}
                        >
                          "{upd.remarks}"
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
