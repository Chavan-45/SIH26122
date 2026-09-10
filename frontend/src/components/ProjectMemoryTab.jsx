import React, { useState, useEffect, useCallback } from 'react';
import {
  History,
  Search,
  Filter,
  RefreshCw,
  AlertCircle,
  Calendar,
  Tag,
  CheckCircle2,
  Clock,
  ChevronRight,
  ChevronLeft,
  X,
  FileText,
  User,
  Shield,
  Layers,
  TrendingUp,
  AlertTriangle,
  Info,
  Check,
  Building2,
  Activity as ActivityIcon,
  FileSpreadsheet,
  Bot,
} from 'lucide-react';
import {
  getMemorySummary,
  getMemoryEvents,
  getActivityMemoryTimeline,
  getActivityDelayAnalysis,
} from '../services/api';

const DISCIPLINES = [
  { value: 'ALL', label: 'All Disciplines' },
  { value: 'CIVIL', label: 'Civil Engineering' },
  { value: 'PIPING', label: 'Piping & Layout' },
  { value: 'ELECTRICAL', label: 'Electrical Systems' },
  { value: 'MECHANICAL', label: 'Mechanical & Rotary' },
  { value: 'INSTRUMENTATION', label: 'Instrumentation & Controls' },
  { value: 'HSE', label: 'HSE & Safety' },
  { value: 'OTHER', label: 'Other Discipline' },
];

const EVENT_TYPES = [
  { value: 'ALL', label: 'All Event Types' },
  { value: 'EXECUTION_UPDATE', label: 'Execution Updates' },
  { value: 'REVIEW_DECISION', label: 'Review Decisions' },
];

const SOURCE_TYPES = [
  { value: 'ALL', label: 'All Sources' },
  { value: 'MANUAL', label: 'Manual Field Report' },
  { value: 'AI_CHAT', label: 'AI Chat Confirmation' },
  { value: 'REPORT_IMPORT', label: 'DPR / Document Import' },
  { value: 'SPREADSHEET', label: 'Spreadsheet Import' },
  { value: 'REVIEW_CENTER', label: 'Review Center Resolution' },
];

export default function ProjectMemoryTab({
  projectId,
  token,
  user,
  project,
  isPlannerOwner,
  assignedDiscipline,
}) {
  // Summary KPI State
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(true);

  // Events Feed State
  const [events, setEvents] = useState([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [eventsError, setEventsError] = useState(null);
  const [totalEvents, setTotalEvents] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const pageSize = 15;

  // Filter States
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedDiscipline, setSelectedDiscipline] = useState(
    !isPlannerOwner && assignedDiscipline ? assignedDiscipline.toUpperCase() : 'ALL'
  );
  const [selectedEventType, setSelectedEventType] = useState('ALL');
  const [selectedSource, setSelectedSource] = useState('ALL');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  // Activity Drawer State
  const [selectedActivityCode, setSelectedActivityCode] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerData, setDrawerData] = useState(null);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [drawerError, setDrawerError] = useState(null);

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Load KPI Summary
  const fetchSummary = useCallback(async () => {
    if (!projectId || !token) return;
    setSummaryLoading(true);
    const res = await getMemorySummary(token, projectId);
    setSummaryLoading(false);
    if (res.success && res.data) {
      setSummary(res.data);
    }
  }, [projectId, token]);

  // Load Filtered Events
  const fetchEvents = useCallback(async () => {
    if (!projectId || !token) return;
    setEventsLoading(true);
    setEventsError(null);

    const params = {
      page,
      page_size: pageSize,
      q: debouncedSearch.trim() || undefined,
      discipline: selectedDiscipline !== 'ALL' ? selectedDiscipline : undefined,
      event_type: selectedEventType !== 'ALL' ? selectedEventType : undefined,
      source: selectedSource !== 'ALL' ? selectedSource : undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    };

    const res = await getMemoryEvents(token, projectId, params);
    setEventsLoading(false);

    if (res.success && res.data) {
      setEvents(res.data.events || []);
      setTotalEvents(res.data.total || 0);
      setTotalPages(res.data.total_pages || 1);
    } else {
      setEventsError(res.error || 'Failed to load historical records');
    }
  }, [
    projectId,
    token,
    page,
    debouncedSearch,
    selectedDiscipline,
    selectedEventType,
    selectedSource,
    dateFrom,
    dateTo,
  ]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  // Handle Opening Activity Memory Drawer
  const handleOpenActivityDrawer = async (activityCode) => {
    if (!activityCode) return;
    setSelectedActivityCode(activityCode);
    setDrawerOpen(true);
    setDrawerLoading(true);
    setDrawerError(null);
    setDrawerData(null);

    const res = await getActivityMemoryTimeline(token, projectId, activityCode);
    setDrawerLoading(false);

    if (res.success && res.data) {
      setDrawerData(res.data);
    } else {
      setDrawerError(res.error || `Could not load memory records for ${activityCode}`);
    }
  };

  const handleCloseDrawer = () => {
    setDrawerOpen(false);
    setSelectedActivityCode(null);
    setDrawerData(null);
  };

  const handleClearFilters = () => {
    setSearchQuery('');
    setDebouncedSearch('');
    if (isPlannerOwner) {
      setSelectedDiscipline('ALL');
    }
    setSelectedEventType('ALL');
    setSelectedSource('ALL');
    setDateFrom('');
    setDateTo('');
    setPage(1);
  };

  const hasActiveFilters =
    debouncedSearch ||
    (isPlannerOwner && selectedDiscipline !== 'ALL') ||
    selectedEventType !== 'ALL' ||
    selectedSource !== 'ALL' ||
    dateFrom ||
    dateTo;

  // Format Date Helper
  const formatDateDisplay = (dateStr) => {
    if (!dateStr) return 'N/A';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString(undefined, {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  const formatDateTimeDisplay = (isoStr) => {
    if (!isoStr) return '';
    try {
      const d = new Date(isoStr);
      return d.toLocaleString(undefined, {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoStr;
    }
  };

  return (
    <div className="pm-workspace-container">
      {/* Top Header */}
      <div className="pm-page-header">
        <div className="pm-header-title-group">
          <div className="pm-title-row">
            <h2 className="pm-main-heading">Project Memory</h2>
            <span className="pm-version-badge">Phase 14 • Institutional Audit</span>
          </div>
          <p className="pm-subtitle">
            Search and review the historical execution record, field progress updates, and review decisions for this project.
          </p>
        </div>

        {project && (
          <div className="pm-project-pill font-mono">
            <Tag size={13} />
            <span>{project.project_code}</span>
            <span className="pm-pill-divider">•</span>
            <span className="pm-pill-name">{project.name}</span>
          </div>
        )}
      </div>

      {/* 4 Summary KPI Cards */}
      <div className="pm-kpi-grid">
        <div className="pm-kpi-card">
          <div className="pm-kpi-header">
            <span className="pm-kpi-label">Execution Updates</span>
            <ActivityIcon size={16} className="pm-kpi-icon text-navy" />
          </div>
          <div className="pm-kpi-value font-mono">
            {summaryLoading ? '...' : (summary?.total_execution_updates ?? 0)}
          </div>
          <div className="pm-kpi-subtext">Append-only field progress logs</div>
        </div>

        <div className="pm-kpi-card">
          <div className="pm-kpi-header">
            <span className="pm-kpi-label">Activities With History</span>
            <Layers size={16} className="pm-kpi-icon text-orange" />
          </div>
          <div className="pm-kpi-value font-mono">
            {summaryLoading ? '...' : (summary?.activities_with_history ?? 0)}
          </div>
          <div className="pm-kpi-subtext">Schedule items with recorded work</div>
        </div>

        <div className="pm-kpi-card">
          <div className="pm-kpi-header">
            <span className="pm-kpi-label">Review Decisions</span>
            <Shield size={16} className="pm-kpi-icon text-blue" />
          </div>
          <div className="pm-kpi-value font-mono">
            {summaryLoading ? '...' : (summary?.total_review_decisions ?? 0)}
          </div>
          <div className="pm-kpi-subtext">Planner resolutions &amp; audits</div>
        </div>

        <div className="pm-kpi-card">
          <div className="pm-kpi-header">
            <span className="pm-kpi-label">History Range</span>
            <Calendar size={16} className="pm-kpi-icon text-green" />
          </div>
          <div className="pm-kpi-value pm-kpi-range-value">
            {summaryLoading
              ? '...'
              : summary?.earliest_date && summary?.latest_date
              ? `${formatDateDisplay(summary.earliest_date)} – ${formatDateDisplay(summary.latest_date)}`
              : 'No history recorded'}
          </div>
          <div className="pm-kpi-subtext">
            Scope: <span className="font-semibold">{summary?.scope || 'Project-wide'}</span>
          </div>
        </div>
      </div>

      {/* Search & Filter Toolbar */}
      <div className="pm-filter-panel">
        {/* Main Search Bar */}
        <div className="pm-search-row">
          <div className="pm-search-input-wrapper">
            <Search size={16} className="pm-search-icon" />
            <input
              type="text"
              className="pm-search-input"
              placeholder="Search activity code (e.g. PIP-201), activity name, remarks or project history..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button
                type="button"
                className="pm-clear-search-btn"
                onClick={() => setSearchQuery('')}
                title="Clear query"
              >
                <X size={14} />
              </button>
            )}
          </div>
        </div>

        {/* Filter Controls Row */}
        <div className="pm-filter-controls-row">
          {/* Discipline Select */}
          <div className="pm-filter-group">
            <label className="pm-filter-label">Discipline</label>
            {isPlannerOwner ? (
              <select
                className="pm-select-control"
                value={selectedDiscipline}
                onChange={(e) => {
                  setSelectedDiscipline(e.target.value);
                  setPage(1);
                }}
              >
                {DISCIPLINES.map((d) => (
                  <option key={d.value} value={d.value}>
                    {d.label}
                  </option>
                ))}
              </select>
            ) : (
              <div className="pm-locked-discipline-pill font-mono">
                <Shield size={12} />
                <span>{assignedDiscipline || 'ASSIGNED'} (Scoped)</span>
              </div>
            )}
          </div>

          {/* Event Type */}
          <div className="pm-filter-group">
            <label className="pm-filter-label">Event Type</label>
            <select
              className="pm-select-control"
              value={selectedEventType}
              onChange={(e) => {
                setSelectedEventType(e.target.value);
                setPage(1);
              }}
            >
              {EVENT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          {/* Source Filter */}
          <div className="pm-filter-group">
            <label className="pm-filter-label">Source</label>
            <select
              className="pm-select-control"
              value={selectedSource}
              onChange={(e) => {
                setSelectedSource(e.target.value);
                setPage(1);
              }}
            >
              {SOURCE_TYPES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>

          {/* Date Range */}
          <div className="pm-filter-group">
            <label className="pm-filter-label">From Date</label>
            <input
              type="date"
              className="pm-date-control"
              value={dateFrom}
              onChange={(e) => {
                setDateFrom(e.target.value);
                setPage(1);
              }}
            />
          </div>

          <div className="pm-filter-group">
            <label className="pm-filter-label">To Date</label>
            <input
              type="date"
              className="pm-date-control"
              value={dateTo}
              onChange={(e) => {
                setDateTo(e.target.value);
                setPage(1);
              }}
            />
          </div>

          {/* Clear Filters Button */}
          {hasActiveFilters && (
            <div className="pm-filter-group pm-clear-group">
              <button
                type="button"
                className="pm-btn-clear-filters"
                onClick={handleClearFilters}
              >
                <X size={14} />
                <span>Clear Filters</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main Results Card */}
      <div className="pm-results-card">
        {/* Results Header */}
        <div className="pm-results-header">
          <div className="pm-results-title-group">
            <h3 className="pm-results-title">Historical Execution Events</h3>
            <span className="pm-count-badge font-mono">
              {eventsLoading ? 'Loading...' : `${totalEvents} Records Found`}
            </span>
          </div>

          {/* Quick Refresh */}
          <button
            type="button"
            className="pm-btn-refresh"
            onClick={() => {
              fetchSummary();
              fetchEvents();
            }}
            disabled={eventsLoading}
            title="Refresh historical timeline"
          >
            <RefreshCw size={14} className={eventsLoading ? 'spin-icon' : ''} />
            <span>Refresh</span>
          </button>
        </div>

        {/* Error State */}
        {eventsError && (
          <div className="pm-error-banner">
            <AlertCircle size={18} className="pm-error-icon" />
            <div className="pm-error-content">
              <h4>Could not load project history</h4>
              <p>{eventsError}</p>
            </div>
            <button
              type="button"
              className="pm-btn-retry"
              onClick={fetchEvents}
            >
              Retry
            </button>
          </div>
        )}

        {/* Loading State */}
        {eventsLoading && (
          <div className="pm-loading-state">
            <RefreshCw size={24} className="spin-icon" />
            <span>Retrieving institutional project memory...</span>
          </div>
        )}

        {/* Empty State */}
        {!eventsLoading && !eventsError && events.length === 0 && (
          <div className="pm-empty-state">
            <History size={40} className="pm-empty-icon" />
            <h4>No historical records match these filters</h4>
            <p>
              {hasActiveFilters
                ? 'Try broadening your search query or clearing the date and discipline filters.'
                : 'No field execution updates or review decisions have been recorded for this project yet.'}
            </p>
            {hasActiveFilters && (
              <button
                type="button"
                className="btn-secondary"
                onClick={handleClearFilters}
              >
                Clear Filters
              </button>
            )}
          </div>
        )}

        {/* Historical Events List */}
        {!eventsLoading && !eventsError && events.length > 0 && (
          <div className="pm-events-list">
            {events.map((ev) => (
              <div key={ev.event_id} className="pm-event-row">
                {/* Date & Time Column */}
                <div className="pm-event-time-col">
                  <span className="pm-event-date font-mono">
                    {formatDateDisplay(ev.event_date)}
                  </span>
                  <span className="pm-event-time">
                    {formatDateTimeDisplay(ev.created_at)}
                  </span>
                </div>

                {/* Event Marker */}
                <div className="pm-event-marker-col">
                  <div className={`pm-event-dot dot-${(ev.update_type || ev.event_type || 'default').toLowerCase()}`} />
                  <div className="pm-event-line" />
                </div>

                {/* Event Content Column */}
                <div className="pm-event-content-col">
                  <div className="pm-event-header-row">
                    <button
                      type="button"
                      className="pm-activity-link-btn"
                      onClick={() => handleOpenActivityDrawer(ev.activity_code)}
                      title={`Open complete history for ${ev.activity_code}`}
                    >
                      <span className="pm-act-code font-mono">{ev.activity_code}</span>
                      <span className="pm-act-name">{ev.activity_name}</span>
                    </button>

                    <div className="pm-event-badges-group">
                      {ev.discipline && (
                        <span className="pm-discipline-badge">
                          {ev.discipline}
                        </span>
                      )}
                      <span className={`pm-source-badge src-${(ev.source || 'manual').toLowerCase()}`}>
                        {ev.source.replace('_', ' ')}
                      </span>
                    </div>
                  </div>

                  <div className="pm-event-title-row">
                    <span className="pm-event-title">{ev.title}</span>
                    {ev.progress_percentage !== null && ev.progress_percentage !== undefined && (
                      <span className="pm-progress-chip font-mono">
                        {ev.progress_percentage}% Recorded
                      </span>
                    )}
                  </div>

                  {ev.remarks && (
                    <div className="pm-event-remarks">
                      <span className="pm-quote-mark">“</span>
                      <span>{ev.remarks}</span>
                      <span className="pm-quote-mark">”</span>
                    </div>
                  )}

                  <div className="pm-event-footer-row">
                    {ev.reported_by && (
                      <div className="pm-reporter-tag">
                        <User size={12} />
                        <span>
                          Reported by <strong className="pm-reporter-name">{ev.reported_by.name}</strong>
                          {ev.reported_by.role && ` (${ev.reported_by.role})`}
                        </span>
                      </div>
                    )}

                    {ev.provenance && (
                      <div className="pm-provenance-tag">
                        <FileText size={12} />
                        <span>
                          {ev.provenance.filename || 'Source Document'}
                          {ev.provenance.page ? ` (Page ${ev.provenance.page})` : ''}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination Bar */}
        {!eventsLoading && !eventsError && totalPages > 1 && (
          <div className="pm-pagination-bar">
            <span className="pm-pagination-info">
              Showing page <strong className="font-mono">{page}</strong> of <strong className="font-mono">{totalPages}</strong> ({totalEvents} total events)
            </span>

            <div className="pm-pagination-btns">
              <button
                type="button"
                className="pm-btn-page"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft size={16} />
                <span>Previous</span>
              </button>
              <button
                type="button"
                className="pm-btn-page"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                <span>Next</span>
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Activity Memory Drawer (Right-side Drawer) */}
      {drawerOpen && (
        <div className="pm-drawer-overlay" onClick={handleCloseDrawer}>
          <div
            className="pm-drawer-panel"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Drawer Header */}
            <div className="pm-drawer-header">
              <div className="pm-drawer-title-group">
                <div className="pm-drawer-code-row">
                  <span className="pm-drawer-code font-mono">{selectedActivityCode}</span>
                  {drawerData?.activity?.discipline && (
                    <span className="pm-discipline-badge">
                      {drawerData.activity.discipline}
                    </span>
                  )}
                  {drawerData?.activity?.current_status && (
                    <span className={`status-pill ${drawerData.activity.current_status.toLowerCase()}`}>
                      <span className="status-dot-small" />
                      <span>{drawerData.activity.current_status.replace('_', ' ')}</span>
                    </span>
                  )}
                </div>
                <h3 className="pm-drawer-name">{drawerData?.activity?.activity_name || selectedActivityCode}</h3>
              </div>

              <button
                type="button"
                className="pm-drawer-close-btn"
                onClick={handleCloseDrawer}
                title="Close drawer"
              >
                <X size={18} />
              </button>
            </div>

            {/* Drawer Body Content */}
            <div className="pm-drawer-body">
              {drawerLoading && (
                <div className="pm-drawer-loading">
                  <RefreshCw size={24} className="spin-icon" />
                  <span>Loading activity memory &amp; delay records...</span>
                </div>
              )}

              {drawerError && (
                <div className="pm-drawer-error">
                  <AlertCircle size={20} />
                  <p>{drawerError}</p>
                </div>
              )}

              {!drawerLoading && !drawerError && drawerData && (
                <>
                  {/* SECTION 1: Schedule Context */}
                  <div className="pm-drawer-section">
                    <h4 className="pm-drawer-section-title">
                      <Calendar size={15} />
                      <span>Schedule Context</span>
                    </h4>
                    <div className="pm-drawer-context-grid">
                      <div className="pm-ctx-item">
                        <span className="pm-ctx-label">Planned Start:</span>
                        <span className="pm-ctx-val font-mono">{formatDateDisplay(drawerData.activity.planned_start)}</span>
                      </div>
                      <div className="pm-ctx-item">
                        <span className="pm-ctx-label">Planned Finish:</span>
                        <span className="pm-ctx-val font-mono">{formatDateDisplay(drawerData.activity.planned_finish)}</span>
                      </div>
                      <div className="pm-ctx-item">
                        <span className="pm-ctx-label">Actual Start:</span>
                        <span className="pm-ctx-val font-mono">{formatDateDisplay(drawerData.activity.actual_start)}</span>
                      </div>
                      <div className="pm-ctx-item">
                        <span className="pm-ctx-label">Actual Finish:</span>
                        <span className="pm-ctx-val font-mono">{formatDateDisplay(drawerData.activity.actual_finish)}</span>
                      </div>
                      <div className="pm-ctx-item">
                        <span className="pm-ctx-label">Current Progress:</span>
                        <span className="pm-ctx-val font-mono font-bold text-navy">
                          {drawerData.activity.current_progress}%
                        </span>
                      </div>
                      <div className="pm-ctx-item">
                        <span className="pm-ctx-label">Current Status:</span>
                        <span className="pm-ctx-val font-mono">{drawerData.activity.current_status}</span>
                      </div>
                    </div>
                  </div>

                  {/* SECTION 2: Schedule Performance (Deterministic Delay Analysis) */}
                  <div className="pm-drawer-section">
                    <h4 className="pm-drawer-section-title">
                      <TrendingUp size={15} />
                      <span>Schedule Performance Fact</span>
                    </h4>
                    <div className={`pm-delay-banner state-${(drawerData.delay_analysis?.state || 'on_time').toLowerCase()}`}>
                      <div className="pm-delay-banner-header">
                        <span className="pm-delay-state-pill font-mono">
                          {drawerData.delay_analysis?.state?.replace('_', ' ')}
                        </span>
                        {drawerData.delay_analysis?.late_days > 0 && (
                          <span className="pm-delay-days-badge font-mono">
                            {drawerData.delay_analysis.late_days} Day(s) Variance
                          </span>
                        )}
                      </div>
                      <p className="pm-delay-summary-text">
                        {drawerData.delay_analysis?.summary}
                      </p>
                    </div>
                  </div>

                  {/* SECTION 3: Recorded Timeline (Chronological Oldest -> Newest) */}
                  <div className="pm-drawer-section">
                    <h4 className="pm-drawer-section-title">
                      <History size={15} />
                      <span>Recorded Chronological Timeline ({drawerData.total_events} Events)</span>
                    </h4>

                    {drawerData.events.length === 0 ? (
                      <p className="pm-empty-text">No recorded events found for this activity.</p>
                    ) : (
                      <div className="pm-drawer-timeline">
                        {drawerData.events.map((ev, idx) => (
                          <div key={ev.event_id || idx} className="pm-drawer-timeline-item">
                            <div className="pm-drawer-timeline-header">
                              <span className="pm-dt-date font-mono">{formatDateDisplay(ev.event_date)}</span>
                              <span className={`pm-dt-type-badge type-${(ev.update_type || 'default').toLowerCase()}`}>
                                {ev.update_type}
                              </span>
                              {ev.progress_percentage !== null && (
                                <span className="pm-dt-prog font-mono">{ev.progress_percentage}%</span>
                              )}
                            </div>

                            <div className="pm-dt-title">{ev.title}</div>

                            {ev.remarks && (
                              <div className="pm-dt-remarks">
                                <em>"{ev.remarks}"</em>
                              </div>
                            )}

                            <div className="pm-dt-meta">
                              {ev.reported_by && (
                                <span>Reported by <strong>{ev.reported_by.name}</strong></span>
                              )}
                              <span className="pm-dt-source-badge">[{ev.source}]</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* SECTION 4: Recorded Notes */}
                  <div className="pm-drawer-section">
                    <h4 className="pm-drawer-section-title">
                      <FileText size={15} />
                      <span>Recorded Project Notes</span>
                    </h4>
                    {drawerData.delay_analysis?.recorded_notes && drawerData.delay_analysis.recorded_notes.length > 0 ? (
                      <ul className="pm-recorded-notes-list">
                        {drawerData.delay_analysis.recorded_notes.map((note, idx) => (
                          <li key={idx} className="pm-note-item">
                            <span className="pm-note-bullet">•</span>
                            <span>"{note}"</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <div className="pm-no-notes-banner">
                        <Info size={15} className="text-gray" />
                        <span>No explanatory notes have been recorded for this activity.</span>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
