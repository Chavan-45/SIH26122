import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  getAnalyticsSummary,
  getAnalyticsTrend,
  getAnalyticsDisciplines,
  getAnalyticsRisks,
  getAnalyticsForecast,
  getAnalyticsCompleted,
} from '../services/api';
import {
  TrendingUp,
  AlertTriangle,
  Clock,
  Calendar,
  Layers,
  RefreshCw,
  Info,
  CheckCircle2,
  AlertCircle,
  Shield,
  Briefcase,
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  Filter,
  Check,
  ChevronRight,
  BarChart3,
  HelpCircle,
} from 'lucide-react';

export default function AnalyticsTab({
  projectId,
  token,
  user,
  project,
  isPlannerOwner,
  assignedDiscipline,
  onSelectActivity,
}) {
  // State variables
  const [summaryData, setSummaryData] = useState(null);
  const [trendData, setTrendData] = useState(null);
  const [trendRange, setTrendRange] = useState('30d');
  const [disciplineData, setDisciplineData] = useState(null);
  const [risksData, setRisksData] = useState(null);
  const [forecastData, setForecastData] = useState(null);
  const [completedData, setCompletedData] = useState(null);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // Filters for Schedule Risk
  const [riskLevelFilter, setRiskLevelFilter] = useState('ALL');
  const [riskDisciplineFilter, setRiskDisciplineFilter] = useState('ALL');

  // Chart Tooltip Hover State
  const [hoveredPointIndex, setHoveredPointIndex] = useState(null);

  // Popover state for risk reasons
  const [activeReasonPopover, setActiveReasonPopover] = useState(null);

  // Fetch all analytics datasets
  const fetchAllAnalytics = useCallback(async (isSilent = false) => {
    if (!isSilent) setRefreshing(true);
    setError(null);

    try {
      const [sumRes, trendRes, discRes, riskRes, fcstRes, compRes] = await Promise.all([
        getAnalyticsSummary(token, projectId),
        getAnalyticsTrend(token, projectId, trendRange),
        getAnalyticsDisciplines(token, projectId),
        getAnalyticsRisks(token, projectId, {
          level: riskLevelFilter,
          discipline: riskDisciplineFilter,
        }),
        getAnalyticsForecast(token, projectId),
        getAnalyticsCompleted(token, projectId),
      ]);

      if (sumRes.success && sumRes.data) setSummaryData(sumRes.data);
      else if (!isSilent) setError(sumRes.error || 'Failed to load analytics summary.');

      if (trendRes.success && trendRes.data) setTrendData(trendRes.data);
      if (discRes.success && discRes.data) setDisciplineData(discRes.data);
      if (riskRes.success && riskRes.data) setRisksData(riskRes.data);
      if (fcstRes.success && fcstRes.data) setForecastData(fcstRes.data);
      if (compRes.success && compRes.data) setCompletedData(compRes.data);
    } catch (err) {
      if (!isSilent) setError('Network error while loading project analytics.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token, projectId, trendRange, riskLevelFilter, riskDisciplineFilter]);

  // Initial load & when filters change
  useEffect(() => {
    fetchAllAnalytics(false);
  }, [fetchAllAnalytics]);

  // Format dates helper
  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  const kpis = summaryData?.kpis;
  const isSupervisor = user?.role === 'SUPERVISOR';
  const effectiveDiscipline = assignedDiscipline || kpis?.scoped_discipline;

  // Chart coordinate calculations for SVG Line / Area chart
  const chartPoints = useMemo(() => {
    if (!trendData?.trend_points || trendData.trend_points.length === 0) return [];
    return trendData.trend_points;
  }, [trendData]);

  const svgDimensions = { width: 800, height: 240, padLeft: 45, padRight: 20, padTop: 20, padBottom: 35 };

  const svgPaths = useMemo(() => {
    if (chartPoints.length === 0) return { actualPath: '', expectedPath: '', actualArea: '', expectedArea: '', points: [] };

    const { width, height, padLeft, padRight, padTop, padBottom } = svgDimensions;
    const plotW = width - padLeft - padRight;
    const plotH = height - padTop - padBottom;
    const count = chartPoints.length;

    const coords = chartPoints.map((pt, i) => {
      const x = count === 1 ? padLeft + plotW / 2 : padLeft + (i / (count - 1)) * plotW;
      const actualY = padTop + plotH - (Math.max(0, Math.min(100, pt.actual_progress)) / 100) * plotH;
      const expectedY = padTop + plotH - (Math.max(0, Math.min(100, pt.expected_progress)) / 100) * plotH;
      return { x, actualY, expectedY, data: pt };
    });

    // Build SVG path commands
    let actualPath = `M ${coords[0].x} ${coords[0].actualY}`;
    let expectedPath = `M ${coords[0].x} ${coords[0].expectedY}`;

    for (let i = 1; i < coords.length; i++) {
      actualPath += ` L ${coords[i].x} ${coords[i].actualY}`;
      expectedPath += ` L ${coords[i].x} ${coords[i].expectedY}`;
    }

    const baselineY = padTop + plotH;
    const actualArea = `${actualPath} L ${coords[coords.length - 1].x} ${baselineY} L ${coords[0].x} ${baselineY} Z`;
    const expectedArea = `${expectedPath} L ${coords[coords.length - 1].x} ${baselineY} L ${coords[0].x} ${baselineY} Z`;

    return { actualPath, expectedPath, actualArea, expectedArea, points: coords };
  }, [chartPoints]);

  if (loading && !summaryData) {
    return (
      <div className="analytics-page">
        <div className="analytics-loading-card">
          <RefreshCw size={28} className="spin-icon" style={{ color: 'var(--color-primary)', marginBottom: '1rem' }} />
          <p style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>Loading Project Analytics &amp; Forecasts...</p>
          <span style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
            Calculating time-based expectations, historical progress trend, and schedule risk indicators...
          </span>
        </div>
      </div>
    );
  }

  if (error && !summaryData) {
    return (
      <div className="analytics-page">
        <div className="analytics-error-card">
          <AlertCircle size={32} style={{ color: 'var(--color-danger)', marginBottom: '0.75rem' }} />
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: '0.5rem' }}>
            Analytics could not be loaded
          </h2>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem', marginBottom: '1.25rem' }}>{error}</p>
          <button type="button" className="btn-primary" onClick={() => fetchAllAnalytics(false)}>
            <RefreshCw size={14} />
            <span>Retry Loading Analytics</span>
          </button>
        </div>
      </div>
    );
  }

  const hasZeroActivities = kpis && kpis.total_activities === 0;

  return (
    <div className="analytics-page">
      {/* HEADER SECTION */}
      <header className="analytics-header">
        <div className="analytics-header-title-group">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            <h1 className="analytics-title">
              {isSupervisor && effectiveDiscipline ? `Project Analytics • ${effectiveDiscipline}` : 'Project Analytics'}
            </h1>
            <span className="analytics-live-badge">
              <span className="analytics-live-dot"></span>
              LIVE PROJECT DATA
            </span>
            {isSupervisor && effectiveDiscipline && (
              <span className="analytics-discipline-badge font-mono">{effectiveDiscipline}</span>
            )}
          </div>
          <p className="analytics-subtitle">
            {isSupervisor
              ? 'Analyze execution performance and schedule risk for your assigned discipline.'
              : 'Analyze project execution trends, schedule variance, risks and indicative completion forecasts.'}
          </p>
        </div>

        <div className="analytics-header-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => fetchAllAnalytics(false)}
            disabled={refreshing}
            title="Refresh analytics data"
          >
            <RefreshCw size={14} className={refreshing ? 'spin-icon' : ''} />
            <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>
      </header>

      {hasZeroActivities ? (
        <section className="analytics-card" style={{ textAlign: 'center', padding: '3.5rem 2rem' }}>
          <Layers size={48} style={{ color: 'var(--color-border-strong)', margin: '0 auto 1rem' }} />
          <h3 style={{ fontSize: '1.25rem', color: 'var(--color-primary)', marginBottom: '0.5rem' }}>
            No Schedule Data Available
          </h3>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem', maxWidth: '480px', margin: '0 auto' }}>
            Import a baseline schedule before analytics and indicative forecasts can be calculated.
          </p>
        </section>
      ) : (
        <>
          {/* TOP 4 KPI CARDS */}
          <section className="analytics-kpi-grid">
            {/* CARD 1: OVERALL PROGRESS */}
            <div className="analytics-kpi-card">
              <div className="analytics-kpi-top">
                <span className="analytics-kpi-label">Overall Progress</span>
                <div className="analytics-kpi-icon-wrapper" style={{ color: 'var(--color-primary)' }}>
                  <TrendingUp size={18} />
                </div>
              </div>
              <div className="analytics-kpi-main">
                <div className="analytics-kpi-value">{kpis?.actual_progress ?? 0}%</div>
                <div className="analytics-kpi-mini-bar-track">
                  <div
                    className="analytics-kpi-mini-bar-fill actual"
                    style={{ width: `${Math.min(100, Math.max(0, kpis?.actual_progress ?? 0))}%` }}
                  ></div>
                </div>
              </div>
              <div className="analytics-kpi-footer">
                <span className="analytics-kpi-subtext">Activity-count weighted</span>
                <span className="analytics-kpi-expected-badge">Expected: {kpis?.expected_progress ?? 0}%</span>
              </div>
            </div>

            {/* CARD 2: SCHEDULE VARIANCE */}
            <div className="analytics-kpi-card">
              <div className="analytics-kpi-top">
                <span className="analytics-kpi-label">Schedule Variance</span>
                <div
                  className="analytics-kpi-icon-wrapper"
                  style={{
                    color:
                      (kpis?.progress_variance_pp ?? 0) >= 0
                        ? 'var(--color-success)'
                        : (kpis?.progress_variance_pp ?? 0) >= -15
                        ? 'var(--color-warning)'
                        : 'var(--color-danger)',
                  }}
                >
                  {(kpis?.progress_variance_pp ?? 0) >= 0 ? <ArrowUpRight size={18} /> : <ArrowDownRight size={18} />}
                </div>
              </div>
              <div className="analytics-kpi-main">
                <div
                  className={`analytics-kpi-value font-mono ${
                    (kpis?.progress_variance_pp ?? 0) >= 0
                      ? 'positive'
                      : (kpis?.progress_variance_pp ?? 0) >= -15
                      ? 'warning'
                      : 'negative'
                  }`}
                >
                  {(kpis?.progress_variance_pp ?? 0) > 0 ? '+' : ''}
                  {kpis?.progress_variance_pp ?? 0} pp
                </div>
              </div>
              <div className="analytics-kpi-footer">
                <span className="analytics-kpi-subtext">
                  {(kpis?.progress_variance_pp ?? 0) >= 0
                    ? 'Ahead of time-based baseline'
                    : (kpis?.progress_variance_pp ?? 0) >= -15
                    ? 'Behind time-based baseline'
                    : 'Materially behind baseline expectation'}
                </span>
              </div>
            </div>

            {/* CARD 3: AT-RISK ACTIVITIES */}
            <div className="analytics-kpi-card">
              <div className="analytics-kpi-top">
                <span className="analytics-kpi-label">At-Risk Activities</span>
                <div
                  className="analytics-kpi-icon-wrapper"
                  style={{
                    color: (kpis?.high_risk_count ?? 0) > 0 ? 'var(--color-danger)' : 'var(--color-warning)',
                  }}
                >
                  <AlertTriangle size={18} />
                </div>
              </div>
              <div className="analytics-kpi-main">
                <div className="analytics-kpi-value font-mono">{kpis?.at_risk_count ?? 0}</div>
              </div>
              <div className="analytics-kpi-footer">
                <span className="analytics-kpi-risk-breakdown">
                  <span className="risk-tag high">{kpis?.high_risk_count ?? 0} High</span>
                  <span className="dot-sep">•</span>
                  <span className="risk-tag medium">{kpis?.medium_risk_count ?? 0} Med</span>
                  <span className="dot-sep">•</span>
                  <span className="risk-tag low">{kpis?.low_risk_count ?? 0} Low</span>
                </span>
              </div>
            </div>

            {/* CARD 4: INDICATIVE COMPLETION */}
            <div className="analytics-kpi-card">
              <div className="analytics-kpi-top">
                <span className="analytics-kpi-label">Indicative Completion</span>
                <div className="analytics-kpi-icon-wrapper" style={{ color: 'var(--color-primary)' }}>
                  <Calendar size={18} />
                </div>
              </div>
              <div className="analytics-kpi-main">
                <div className="analytics-kpi-value date-value">
                  {kpis?.indicative_completion_date ? formatDate(kpis.indicative_completion_date) : 'Insufficient History'}
                </div>
              </div>
              <div className="analytics-kpi-footer">
                {kpis?.indicative_variance_days !== null && kpis?.indicative_variance_days !== undefined ? (
                  <span
                    className={`analytics-kpi-subtext font-mono ${
                      kpis.indicative_variance_days > 0 ? 'text-warning' : 'text-success'
                    }`}
                  >
                    {kpis.indicative_variance_days > 0 ? `+${kpis.indicative_variance_days}` : kpis.indicative_variance_days}{' '}
                    days vs baseline
                  </span>
                ) : (
                  <span className="analytics-kpi-subtext">Baseline fallback</span>
                )}
                <span className="analytics-kpi-coverage-badge">
                  Coverage: {kpis?.forecast_coverage_count ?? 0}/{kpis?.incomplete_activity_count ?? 0} active
                </span>
              </div>
            </div>
          </section>

          {/* METHODOLOGY DISCLAIMER STRIP */}
          <div className="analytics-disclaimer-strip">
            <Info size={16} className="disclaimer-icon" />
            <span>
              Forecasting uses observed progress rates and time-based schedule expectations. It does not perform CPM
              critical-path analysis.
            </span>
          </div>

          {/* SECTION 1: PROGRESS TREND */}
          <section className="analytics-card analytics-trend-section">
            <div className="analytics-card-header">
              <div>
                <h2 className="analytics-card-title">Progress Trend</h2>
                <p className="analytics-card-subtitle">Actual execution compared with time-based expected progress.</p>
              </div>

              <div className="analytics-segmented-control" role="group" aria-label="Progress trend range selector">
                {['7d', '30d', '90d', 'all'].map((rng) => (
                  <button
                    key={rng}
                    type="button"
                    className={`analytics-segment-btn ${trendRange === rng ? 'active' : ''}`}
                    onClick={() => setTrendRange(rng)}
                  >
                    {rng.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            <div className="analytics-card-body">
              {chartPoints.length === 0 ? (
                <div className="analytics-chart-empty">
                  <BarChart3 size={36} style={{ color: 'var(--color-border-strong)', marginBottom: '0.5rem' }} />
                  <p>Not enough progress history yet.</p>
                  <span>Log progress updates to build the historical execution trend.</span>
                </div>
              ) : (
                <div className="analytics-chart-wrapper">
                  <div className="analytics-chart-legend">
                    <div className="legend-item">
                      <span className="legend-dot actual"></span>
                      <span>Actual Progress (Count-Weighted)</span>
                    </div>
                    <div className="legend-item">
                      <span className="legend-dot expected"></span>
                      <span>Time-Based Expected</span>
                    </div>
                  </div>

                  <div className="analytics-svg-container" style={{ position: 'relative', width: '100%', height: '240px' }}>
                    <svg
                      viewBox={`0 0 ${svgDimensions.width} ${svgDimensions.height}`}
                      className="analytics-trend-svg"
                      preserveAspectRatio="none"
                      onMouseLeave={() => setHoveredPointIndex(null)}
                    >
                      <defs>
                        <linearGradient id="actualGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#17324D" stopOpacity="0.18" />
                          <stop offset="100%" stopColor="#17324D" stopOpacity="0.0" />
                        </linearGradient>
                        <linearGradient id="expectedGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#E97A1F" stopOpacity="0.12" />
                          <stop offset="100%" stopColor="#E97A1F" stopOpacity="0.0" />
                        </linearGradient>
                      </defs>

                      {/* Horizontal Grid lines */}
                      {[0, 25, 50, 75, 100].map((pct) => {
                        const y =
                          svgDimensions.padTop +
                          (svgDimensions.height - svgDimensions.padTop - svgDimensions.padBottom) * (1 - pct / 100);
                        return (
                          <g key={pct}>
                            <line
                              x1={svgDimensions.padLeft}
                              y1={y}
                              x2={svgDimensions.width - svgDimensions.padRight}
                              y2={y}
                              stroke="var(--color-border-subtle)"
                              strokeWidth="1"
                              strokeDasharray={pct === 0 || pct === 100 ? 'none' : '3 3'}
                            />
                            <text
                              x={svgDimensions.padLeft - 8}
                              y={y + 3}
                              textAnchor="end"
                              fontSize="10"
                              fill="var(--color-text-muted)"
                              fontFamily="var(--font-mono)"
                            >
                              {pct}%
                            </text>
                          </g>
                        );
                      })}

                      {/* Area Fills */}
                      {svgPaths.expectedArea && (
                        <path d={svgPaths.expectedArea} fill="url(#expectedGradient)" />
                      )}
                      {svgPaths.actualArea && (
                        <path d={svgPaths.actualArea} fill="url(#actualGradient)" />
                      )}

                      {/* Line Paths */}
                      {svgPaths.expectedPath && (
                        <path
                          d={svgPaths.expectedPath}
                          fill="none"
                          stroke="#E97A1F"
                          strokeWidth="2"
                          strokeDasharray="4 3"
                        />
                      )}
                      {svgPaths.actualPath && (
                        <path
                          d={svgPaths.actualPath}
                          fill="none"
                          stroke="#17324D"
                          strokeWidth="2.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      )}

                      {/* Hover Target Columns & Points */}
                      {svgPaths.points.map((pt, idx) => {
                        const isHovered = hoveredPointIndex === idx;
                        return (
                          <g key={idx}>
                            {/* Transparent interaction bar */}
                            <rect
                              x={pt.x - (svgDimensions.width / chartPoints.length) / 2}
                              y={svgDimensions.padTop}
                              width={svgDimensions.width / chartPoints.length}
                              height={svgDimensions.height - svgDimensions.padTop - svgDimensions.padBottom}
                              fill="transparent"
                              style={{ cursor: 'pointer' }}
                              onMouseEnter={() => setHoveredPointIndex(idx)}
                            />

                            {/* Active vertical rule & point marker */}
                            {isHovered && (
                              <>
                                <line
                                  x1={pt.x}
                                  y1={svgDimensions.padTop}
                                  x2={pt.x}
                                  y2={svgDimensions.height - svgDimensions.padBottom}
                                  stroke="var(--color-primary)"
                                  strokeWidth="1"
                                  strokeDasharray="2 2"
                                />
                                <circle cx={pt.x} cy={pt.expectedY} r="4" fill="#E97A1F" stroke="#fff" strokeWidth="2" />
                                <circle cx={pt.x} cy={pt.actualY} r="4.5" fill="#17324D" stroke="#fff" strokeWidth="2" />
                              </>
                            )}
                          </g>
                        );
                      })}

                      {/* X-axis date labels */}
                      {svgPaths.points
                        .filter((_, i) => {
                          const len = svgPaths.points.length;
                          if (len <= 7) return true;
                          if (len <= 14) return i % 2 === 0 || i === len - 1;
                          if (len <= 30) return i % 5 === 0 || i === len - 1;
                          return i % 15 === 0 || i === len - 1;
                        })
                        .map((pt, i) => (
                          <text
                            key={i}
                            x={pt.x}
                            y={svgDimensions.height - 10}
                            textAnchor="middle"
                            fontSize="10"
                            fill="var(--color-text-secondary)"
                            fontFamily="var(--font-mono)"
                          >
                            {formatDate(pt.data.date).split(' ').slice(0, 2).join(' ')}
                          </text>
                        ))}
                    </svg>

                    {/* Interactive Tooltip Card */}
                    {hoveredPointIndex !== null && svgPaths.points[hoveredPointIndex] && (
                      <div
                        className="analytics-chart-tooltip"
                        style={{
                          left: `${(svgPaths.points[hoveredPointIndex].x / svgDimensions.width) * 100}%`,
                          transform:
                            svgPaths.points[hoveredPointIndex].x > svgDimensions.width * 0.7
                              ? 'translateX(-105%)'
                              : 'translateX(10px)',
                        }}
                      >
                        <div className="tooltip-date font-mono">
                          {formatDate(svgPaths.points[hoveredPointIndex].data.date)}
                        </div>
                        <div className="tooltip-row">
                          <span className="tooltip-label">
                            <span className="tooltip-indicator actual"></span> Actual:
                          </span>
                          <span className="tooltip-value font-mono">
                            {svgPaths.points[hoveredPointIndex].data.actual_progress}%
                          </span>
                        </div>
                        <div className="tooltip-row">
                          <span className="tooltip-label">
                            <span className="tooltip-indicator expected"></span> Expected:
                          </span>
                          <span className="tooltip-value font-mono">
                            {svgPaths.points[hoveredPointIndex].data.expected_progress}%
                          </span>
                        </div>
                        <div className="tooltip-row variance-row">
                          <span className="tooltip-label">Variance:</span>
                          <span
                            className={`tooltip-value font-mono ${
                              svgPaths.points[hoveredPointIndex].data.progress_variance_pp >= 0
                                ? 'text-success'
                                : 'text-danger'
                            }`}
                          >
                            {svgPaths.points[hoveredPointIndex].data.progress_variance_pp > 0 ? '+' : ''}
                            {svgPaths.points[hoveredPointIndex].data.progress_variance_pp} pp
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* SECTION 2: DISCIPLINE PERFORMANCE */}
          <section className="analytics-card">
            <div className="analytics-card-header">
              <div>
                <h2 className="analytics-card-title">Discipline Performance</h2>
                <p className="analytics-card-subtitle">
                  Actual progress compared with time-based schedule expectation across project disciplines.
                </p>
              </div>
            </div>

            <div className="analytics-card-body">
              {(!disciplineData?.disciplines || disciplineData.disciplines.length === 0) ? (
                <div className="analytics-empty-message">No discipline data recorded yet.</div>
              ) : (
                <div className="analytics-discipline-list">
                  {disciplineData.disciplines.map((d) => (
                    <div key={d.discipline} className="analytics-discipline-row">
                      <div className="discipline-meta-col">
                        <div className="discipline-title-row">
                          <span className="discipline-name font-mono">{d.discipline}</span>
                          <span className="discipline-total-badge">{d.total_activities} activities</span>
                        </div>
                        <div className="discipline-tags-row">
                          {d.overdue_count > 0 && (
                            <span className="tag-overdue font-mono">{d.overdue_count} Overdue</span>
                          )}
                          {d.at_risk_count > 0 && (
                            <span className="tag-at-risk font-mono">{d.at_risk_count} At Risk</span>
                          )}
                          <span className="tag-completed font-mono">{d.completed} Done</span>
                        </div>
                      </div>

                      <div className="discipline-bars-col">
                        {/* Actual bar */}
                        <div className="progress-bar-group">
                          <div className="progress-bar-label-row">
                            <span className="bar-title">Actual Execution</span>
                            <span className="bar-pct font-mono">{d.actual_progress}%</span>
                          </div>
                          <div className="bar-track">
                            <div
                              className="bar-fill actual"
                              style={{ width: `${Math.min(100, Math.max(0, d.actual_progress))}%` }}
                            ></div>
                          </div>
                        </div>

                        {/* Expected bar */}
                        <div className="progress-bar-group">
                          <div className="progress-bar-label-row">
                            <span className="bar-title">Time-Based Expected</span>
                            <span className="bar-pct font-mono">{d.expected_progress}%</span>
                          </div>
                          <div className="bar-track">
                            <div
                              className="bar-fill expected"
                              style={{ width: `${Math.min(100, Math.max(0, d.expected_progress))}%` }}
                            ></div>
                          </div>
                        </div>
                      </div>

                      <div className="discipline-variance-col">
                        <span className="variance-label">Variance</span>
                        <div
                          className={`variance-badge font-mono ${
                            d.progress_variance_pp >= 0
                              ? 'positive'
                              : d.progress_variance_pp >= -15
                              ? 'warning'
                              : 'negative'
                          }`}
                        >
                          {d.progress_variance_pp > 0 ? '+' : ''}
                          {d.progress_variance_pp} pp
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* SECTION 3: SCHEDULE RISK */}
          <section className="analytics-card">
            <div className="analytics-card-header" style={{ flexWrap: 'wrap', gap: '1rem' }}>
              <div>
                <h2 className="analytics-card-title">Schedule Risk</h2>
                <p className="analytics-card-subtitle">
                  Activities requiring attention based on current execution, overdue conditions, and progress lags.
                </p>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                {/* Risk Level filter pills */}
                <div className="analytics-segmented-control" role="group" aria-label="Risk level filter">
                  {[
                    { key: 'ALL', label: `All (${risksData?.total_at_risk ?? 0})` },
                    { key: 'HIGH', label: `High (${risksData?.high_count ?? 0})` },
                    { key: 'MEDIUM', label: `Medium (${risksData?.medium_count ?? 0})` },
                    { key: 'LOW', label: `Low (${risksData?.low_count ?? 0})` },
                  ].map((lvl) => (
                    <button
                      key={lvl.key}
                      type="button"
                      className={`analytics-segment-btn ${riskLevelFilter === lvl.key ? 'active' : ''}`}
                      onClick={() => setRiskLevelFilter(lvl.key)}
                    >
                      {lvl.label}
                    </button>
                  ))}
                </div>

                {/* Planner discipline filter dropdown */}
                {!isSupervisor && (
                  <div className="analytics-discipline-select-wrap">
                    <Filter size={14} style={{ color: 'var(--color-text-secondary)' }} />
                    <select
                      value={riskDisciplineFilter}
                      onChange={(e) => setRiskDisciplineFilter(e.target.value)}
                      className="analytics-select"
                      aria-label="Filter risk by discipline"
                    >
                      <option value="ALL">All Disciplines</option>
                      {disciplineData?.disciplines?.map((dp) => (
                        <option key={dp.discipline} value={dp.discipline}>
                          {dp.discipline}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            </div>

            <div className="analytics-card-body" style={{ padding: 0 }}>
              {(!risksData?.items || risksData.items.length === 0) ? (
                <div className="analytics-no-risk-state">
                  <CheckCircle2 size={32} style={{ color: 'var(--color-success)', marginBottom: '0.5rem' }} />
                  <h4>✓ No Significant Schedule Risks Detected</h4>
                  <p>Based on current rule-based indicators and reported progress.</p>
                </div>
              ) : (
                <div className="analytics-table-wrapper">
                  <table className="analytics-table">
                    <thead>
                      <tr>
                        <th>Activity</th>
                        <th>Discipline</th>
                        <th>Progress</th>
                        <th>Expected</th>
                        <th>Variance</th>
                        <th>Planned Finish</th>
                        <th>Forecast Finish</th>
                        <th>Risk Level</th>
                        <th>Primary Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {risksData.items.map((r) => {
                        const hasMultipleReasons = r.risk_reasons && r.risk_reasons.length > 1;
                        const isPopoverOpen = activeReasonPopover === r.activity_id;

                        return (
                          <tr key={r.activity_id} className="analytics-table-row">
                            {/* Activity Code & Name */}
                            <td style={{ minWidth: '180px' }}>
                              <div
                                className="activity-cell-clickable"
                                onClick={() => onSelectActivity && onSelectActivity(r.activity_id)}
                                title="Click to view activity execution detail"
                              >
                                <span className="activity-code-tag font-mono">{r.activity_code}</span>
                                <span className="activity-name-text">{r.activity_name}</span>
                              </div>
                            </td>

                            {/* Discipline */}
                            <td>
                              <span className="discipline-tag-small font-mono">{r.discipline}</span>
                            </td>

                            {/* Progress */}
                            <td className="font-mono">{r.current_progress}%</td>

                            {/* Expected */}
                            <td className="font-mono text-muted">{r.expected_progress}%</td>

                            {/* Variance */}
                            <td>
                              <span
                                className={`variance-inline font-mono ${
                                  r.progress_variance_pp >= 0
                                    ? 'positive'
                                    : r.progress_variance_pp >= -15
                                    ? 'warning'
                                    : 'negative'
                                }`}
                              >
                                {r.progress_variance_pp > 0 ? '+' : ''}
                                {r.progress_variance_pp} pp
                              </span>
                            </td>

                            {/* Planned Finish */}
                            <td className="font-mono text-muted">{formatDate(r.planned_finish)}</td>

                            {/* Forecast Finish */}
                            <td className="font-mono">
                              {r.forecast_finish ? (
                                <span
                                  className={
                                    r.forecast_variance_days && r.forecast_variance_days > 0
                                      ? 'text-warning'
                                      : 'text-success'
                                  }
                                >
                                  {formatDate(r.forecast_finish)}
                                </span>
                              ) : (
                                <span className="text-muted">—</span>
                              )}
                            </td>

                            {/* Risk Badge */}
                            <td>
                              <span className={`risk-badge-pill ${r.risk_level.toLowerCase()}`}>
                                {r.risk_level}
                              </span>
                            </td>

                            {/* Primary Reason + Popover */}
                            <td style={{ position: 'relative', minWidth: '220px' }}>
                              <div className="reason-cell-content">
                                <span className="primary-reason-text">
                                  {r.risk_reasons?.[0] || 'No specific warning'}
                                </span>
                                {hasMultipleReasons && (
                                  <button
                                    type="button"
                                    className="more-reasons-btn"
                                    onClick={() =>
                                      setActiveReasonPopover(isPopoverOpen ? null : r.activity_id)
                                    }
                                  >
                                    +{r.risk_reasons.length - 1} more
                                  </button>
                                )}
                              </div>

                              {/* Multi-reason Popover */}
                              {isPopoverOpen && (
                                <div className="reasons-popover-card">
                                  <div className="popover-header">
                                    <span className="font-mono">{r.activity_code}</span> — Risk Factors
                                  </div>
                                  <ul className="popover-list">
                                    {r.risk_reasons.map((rs, idx) => (
                                      <li key={idx}>• {rs}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>

          {/* SECTION 4: ACTIVITY FORECASTS */}
          <section className="analytics-card">
            <div className="analytics-card-header">
              <div>
                <h2 className="analytics-card-title">Activity Forecasts</h2>
                <p className="analytics-card-subtitle">
                  Indicative finish dates derived deterministically from recent progress velocity.
                </p>
              </div>

              {forecastData && (
                <div className="forecast-header-metric font-mono">
                  Coverage: {forecastData.forecast_coverage_count} / {forecastData.incomplete_activity_count} Incomplete
                  ({forecastData.forecast_coverage_pct}%)
                </div>
              )}
            </div>

            <div className="analytics-card-body" style={{ padding: 0 }}>
              {(!forecastData?.forecasts || forecastData.forecasts.length === 0) ? (
                <div className="analytics-empty-message">No active incomplete activities to forecast.</div>
              ) : (
                <div className="analytics-table-wrapper">
                  <table className="analytics-table">
                    <thead>
                      <tr>
                        <th>Activity</th>
                        <th>Status</th>
                        <th>Current Progress</th>
                        <th>Progress Rate</th>
                        <th>Planned Finish</th>
                        <th>Indicative Finish</th>
                        <th>Variance</th>
                        <th>Data Quality</th>
                      </tr>
                    </thead>
                    <tbody>
                      {forecastData.forecasts.map((f) => (
                        <tr key={f.activity_id} className="analytics-table-row">
                          {/* Activity */}
                          <td style={{ minWidth: '180px' }}>
                            <div
                              className="activity-cell-clickable"
                              onClick={() => onSelectActivity && onSelectActivity(f.activity_id)}
                            >
                              <span className="activity-code-tag font-mono">{f.activity_code}</span>
                              <span className="activity-name-text">{f.activity_name}</span>
                            </div>
                          </td>

                          {/* Status */}
                          <td>
                            <span className={`status-pill-small ${f.execution_status.toLowerCase()}`}>
                              {f.execution_status.replace('_', ' ')}
                            </span>
                          </td>

                          {/* Current Progress */}
                          <td className="font-mono">{f.current_progress}%</td>

                          {/* Progress Rate */}
                          <td className="font-mono">
                            {f.progress_rate_pp_per_day !== null && f.progress_rate_pp_per_day !== undefined ? (
                              <span>{f.progress_rate_pp_per_day} pp/day</span>
                            ) : (
                              <span className="text-muted">—</span>
                            )}
                          </td>

                          {/* Planned Finish */}
                          <td className="font-mono text-muted">{formatDate(f.planned_finish)}</td>

                          {/* Indicative Finish */}
                          <td className="font-mono">
                            {f.indicative_finish ? (
                              <span className="indicative-finish-text">{formatDate(f.indicative_finish)}</span>
                            ) : (
                              <span className="text-muted">
                                {f.forecast_status === 'ON_HOLD'
                                  ? 'On Hold'
                                  : f.forecast_status === 'NOT_STARTED'
                                  ? 'Not Started'
                                  : f.forecast_status === 'UNRELIABLE'
                                  ? 'Unreliable (>365d)'
                                  : 'Insufficient History'}
                              </span>
                            )}
                          </td>

                          {/* Variance */}
                          <td className="font-mono">
                            {f.forecast_variance_days !== null && f.forecast_variance_days !== undefined ? (
                              <span
                                className={
                                  f.forecast_variance_days > 0
                                    ? 'text-warning'
                                    : f.forecast_variance_days < 0
                                    ? 'text-success'
                                    : 'text-muted'
                                }
                              >
                                {f.forecast_variance_days > 0 ? `+${f.forecast_variance_days}` : f.forecast_variance_days} d
                              </span>
                            ) : (
                              <span className="text-muted">—</span>
                            )}
                          </td>

                          {/* Data Quality */}
                          <td>
                            <span className={`data-quality-badge ${f.data_quality.toLowerCase()}`}>
                              {f.data_quality}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>

          {/* SECTION 5: COMPLETED ACTIVITY PERFORMANCE */}
          {completedData && completedData.total_completed > 0 && (
            <section className="analytics-card">
              <div className="analytics-card-header">
                <div>
                  <h2 className="analytics-card-title">Completed Activity Performance</h2>
                  <p className="analytics-card-subtitle">
                    Historical finish adherence for fully closed activities.
                  </p>
                </div>
              </div>

              <div className="analytics-card-body">
                <div className="completed-summary-grid">
                  <div className="completed-kpi-item">
                    <span className="item-label">Total Completed</span>
                    <span className="item-val font-mono">{completedData.total_completed}</span>
                  </div>
                  <div className="completed-kpi-item">
                    <span className="item-label">On Time / Early</span>
                    <span className="item-val font-mono text-success">
                      {completedData.completed_on_time_or_early}
                    </span>
                  </div>
                  <div className="completed-kpi-item">
                    <span className="item-label">Completed Late</span>
                    <span className="item-val font-mono text-warning">
                      {completedData.completed_late}
                    </span>
                  </div>
                  <div className="completed-kpi-item">
                    <span className="item-label">Avg Finish Variance</span>
                    <span className="item-val font-mono">
                      {completedData.average_finish_variance_days !== null &&
                      completedData.average_finish_variance_days !== undefined
                        ? `${completedData.average_finish_variance_days > 0 ? '+' : ''}${
                            completedData.average_finish_variance_days
                          } days`
                        : '0 days'}
                    </span>
                  </div>
                </div>

                {completedData.completed_activities && completedData.completed_activities.length > 0 && (
                  <div className="analytics-table-wrapper" style={{ marginTop: '1.25rem' }}>
                    <table className="analytics-table">
                      <thead>
                        <tr>
                          <th>Activity</th>
                          <th>Discipline</th>
                          <th>Planned Finish</th>
                          <th>Actual Finish</th>
                          <th>Finish Variance</th>
                          <th>Result</th>
                        </tr>
                      </thead>
                      <tbody>
                        {completedData.completed_activities.slice(0, 8).map((c) => (
                          <tr key={c.activity_id} className="analytics-table-row">
                            <td style={{ minWidth: '180px' }}>
                              <div
                                className="activity-cell-clickable"
                                onClick={() => onSelectActivity && onSelectActivity(c.activity_id)}
                              >
                                <span className="activity-code-tag font-mono">{c.activity_code}</span>
                                <span className="activity-name-text">{c.activity_name}</span>
                              </div>
                            </td>
                            <td>
                              <span className="discipline-tag-small font-mono">{c.discipline}</span>
                            </td>
                            <td className="font-mono text-muted">{formatDate(c.planned_finish)}</td>
                            <td className="font-mono">{formatDate(c.actual_finish)}</td>
                            <td className="font-mono">
                              <span className={c.finish_variance_days > 0 ? 'text-warning' : 'text-success'}>
                                {c.finish_variance_days > 0 ? `+${c.finish_variance_days}` : c.finish_variance_days} days
                              </span>
                            </td>
                            <td>
                              <span className={`result-tag ${c.is_late ? 'late' : 'on-time'}`}>
                                {c.is_late ? 'Completed Late' : 'On Time / Early'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
