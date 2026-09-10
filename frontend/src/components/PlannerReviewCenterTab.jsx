import React, { useState, useEffect, useCallback } from 'react';
import {
  ClipboardCheck,
  Search,
  Filter,
  RefreshCw,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  CheckCircle,
  HelpCircle,
  Clock,
  User,
  Building2,
  Tag,
  Calendar,
  Layers,
  ArrowRight,
  Shield,
  Briefcase,
  X,
  Check,
  RotateCcw,
  Sparkles,
  FileSpreadsheet,
  Bot,
  ChevronLeft,
  ChevronRight,
  Info,
} from 'lucide-react';
import {
  getPlannerReviewSummary,
  getPlannerReviewCases,
  getPlannerReviewCaseDetail,
  selectPlannerReviewActivity,
  rejectPlannerReviewCase,
  markPlannerReviewUnplanned,
  applyPlannerReviewCase,
  getActivities,
} from '../services/api';

const DISCIPLINES = [
  'CIVIL',
  'PIPING',
  'ELECTRICAL',
  'MECHANICAL',
  'INSTRUMENTATION',
  'HSE',
  'OTHER',
];

export default function PlannerReviewCenterTab({ projectId, token, user }) {
  // Summary state
  const [summary, setSummary] = useState({
    needs_review: 0,
    low_confidence: 0,
    unmatched: 0,
    resolved: 0,
    unplanned: 0,
    rejected: 0,
    applied: 0,
    total: 0,
  });
  const [summaryLoading, setSummaryLoading] = useState(true);

  // List / Filter states
  const [cases, setCases] = useState([]);
  const [casesLoading, setCasesLoading] = useState(true);
  const [casesTotal, setCasesTotal] = useState(0);
  const [casesPage, setCasesPage] = useState(1);
  const [casesTotalPages, setCasesTotalPages] = useState(1);

  const [statusFilter, setStatusFilter] = useState('ALL');
  const [sourceFilter, setSourceFilter] = useState('ALL');
  const [disciplineFilter, setDisciplineFilter] = useState('ALL');
  const [confidenceFilter, setConfidenceFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  // Selected Case Detail State
  const [selectedCaseId, setSelectedCaseId] = useState(null);
  const [caseDetail, setCaseDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');

  // Activity Linking & Manual Search state
  const [selectedActivityId, setSelectedActivityId] = useState(null);
  const [linkReason, setLinkReason] = useState('');
  const [isLinking, setIsLinking] = useState(false);

  const [manualSearchQuery, setManualSearchQuery] = useState('');
  const [manualSearchResults, setManualSearchResults] = useState([]);
  const [manualSearchLoading, setManualSearchLoading] = useState(false);

  // Decision Modal States (Reject / Mark Unplanned / Apply Confirmation)
  const [modalType, setModalType] = useState(null); // 'REJECT' | 'UNPLANNED' | 'APPLY_CONFIRM'
  const [actionReason, setActionReason] = useState('');
  const [actionError, setActionError] = useState('');
  const [isProcessingAction, setIsProcessingAction] = useState(false);
  const [actionSuccessMsg, setActionSuccessMsg] = useState('');

  // Fetch Summary
  const fetchSummary = useCallback(async () => {
    if (!token || !projectId) return;
    try {
      setSummaryLoading(true);
      const res = await getPlannerReviewSummary(token, projectId);
      if (res.success && res.data) {
        setSummary(res.data);
      }
    } catch (err) {
      console.error('Failed to load review summary:', err);
    } finally {
      setSummaryLoading(false);
    }
  }, [token, projectId]);

  // Fetch Cases List
  const fetchCases = useCallback(
    async (page = 1) => {
      if (!token || !projectId) return;
      try {
        setCasesLoading(true);
        const res = await getPlannerReviewCases(token, projectId, {
          page,
          pageSize: 20,
          status: statusFilter,
          source: sourceFilter,
          discipline: disciplineFilter,
          confidence: confidenceFilter,
          search: searchQuery,
        });
        if (res.success && res.data) {
          setCases(res.data.items || []);
          setCasesTotal(res.data.total || 0);
          setCasesPage(res.data.page || 1);
          setCasesTotalPages(res.data.total_pages || 1);
        }
      } catch (err) {
        console.error('Failed to load review cases:', err);
      } finally {
        setCasesLoading(false);
      }
    },
    [token, projectId, statusFilter, sourceFilter, disciplineFilter, confidenceFilter, searchQuery]
  );

  // Initial load & filter change
  useEffect(() => {
    fetchSummary();
    fetchCases(1);
  }, [fetchSummary, fetchCases]);

  // Load Case Detail
  const loadCaseDetail = async (caseId) => {
    if (!token || !projectId || !caseId) return;
    try {
      setSelectedCaseId(caseId);
      setDetailLoading(true);
      setDetailError('');
      setActionSuccessMsg('');
      setManualSearchQuery('');
      setManualSearchResults([]);

      const res = await getPlannerReviewCaseDetail(token, projectId, caseId);
      if (res.success && res.data) {
        setCaseDetail(res.data);
        setSelectedActivityId(res.data.selected_activity_id || res.data.original_activity_id || null);
        setLinkReason(res.data.review_reason || '');
      } else {
        setDetailError(res.error || 'Failed to load review case detail');
      }
    } catch (err) {
      setDetailError(err.message || 'Error fetching review case');
    } finally {
      setDetailLoading(false);
    }
  };

  // Close Drawer
  const closeDetailDrawer = () => {
    setSelectedCaseId(null);
    setCaseDetail(null);
    setModalType(null);
    setActionReason('');
    setActionError('');
    setActionSuccessMsg('');
  };

  // Search All Project Activities
  const handleManualActivitySearch = async (queryText) => {
    setManualSearchQuery(queryText);
    if (!queryText || queryText.trim().length < 2) {
      setManualSearchResults([]);
      return;
    }
    try {
      setManualSearchLoading(true);
      const res = await getActivities(token, projectId, {
        page: 1,
        pageSize: 15,
        search: queryText.trim(),
        discipline: 'ALL',
        scheduleLevel: 'ALL',
      });
      if (res.success && res.data) {
        setManualSearchResults(res.data.items || []);
      }
    } catch (err) {
      console.error('Failed to search project activities:', err);
    } finally {
      setManualSearchLoading(false);
    }
  };

  // Action 1: Link Activity (RESOLVED)
  const handleLinkActivity = async () => {
    if (!selectedActivityId) {
      setDetailError('Please select a schedule activity from suggestions or search results.');
      return;
    }
    try {
      setIsLinking(true);
      setDetailError('');
      const res = await selectPlannerReviewActivity(
        token,
        projectId,
        selectedCaseId,
        selectedActivityId,
        linkReason.trim() || null
      );
      if (res.success && res.data) {
        setCaseDetail(res.data);
        setActionSuccessMsg('Activity linked successfully. You may now review validation and apply update.');
        fetchSummary();
        fetchCases(casesPage);
      } else {
        setDetailError(res.error || 'Failed to link activity.');
      }
    } catch (err) {
      setDetailError(err.message || 'Error linking activity');
    } finally {
      setIsLinking(false);
    }
  };

  // Action 2: Reject Case
  const handleRejectCase = async () => {
    if (!actionReason.trim() || actionReason.trim().length < 3) {
      setActionError('A valid reason (min 3 characters) is required to reject this update.');
      return;
    }
    try {
      setIsProcessingAction(true);
      setActionError('');
      const res = await rejectPlannerReviewCase(token, projectId, selectedCaseId, actionReason.trim());
      if (res.success && res.data) {
        setCaseDetail(res.data);
        setModalType(null);
        setActionReason('');
        setActionSuccessMsg('Update has been rejected. It will not affect baseline execution.');
        fetchSummary();
        fetchCases(casesPage);
      } else {
        setActionError(res.error || 'Failed to reject case.');
      }
    } catch (err) {
      setActionError(err.message || 'Error rejecting case');
    } finally {
      setIsProcessingAction(false);
    }
  };

  // Action 3: Mark as Unplanned Work
  const handleMarkUnplanned = async () => {
    if (!actionReason.trim() || actionReason.trim().length < 3) {
      setActionError('A valid reason (min 3 characters) is required for classifying unplanned work.');
      return;
    }
    try {
      setIsProcessingAction(true);
      setActionError('');
      const res = await markPlannerReviewUnplanned(token, projectId, selectedCaseId, actionReason.trim());
      if (res.success && res.data) {
        setCaseDetail(res.data);
        setModalType(null);
        setActionReason('');
        setActionSuccessMsg('Work marked as unplanned. Baseline schedule remains protected.');
        fetchSummary();
        fetchCases(casesPage);
      } else {
        setActionError(res.error || 'Failed to mark unplanned work.');
      }
    } catch (err) {
      setActionError(err.message || 'Error marking unplanned');
    } finally {
      setIsProcessingAction(false);
    }
  };

  // Action 4: Apply Resolved Update
  const handleApplyUpdate = async () => {
    try {
      setIsProcessingAction(true);
      setActionError('');
      const res = await applyPlannerReviewCase(token, projectId, selectedCaseId);
      if (res.success && res.data) {
        setCaseDetail(res.data);
        setModalType(null);
        setActionSuccessMsg('Progress update applied successfully to actual project execution.');
        fetchSummary();
        fetchCases(casesPage);
      } else {
        setActionError(res.error || 'Failed to apply update.');
      }
    } catch (err) {
      setActionError(err.message || 'Error applying update');
    } finally {
      setIsProcessingAction(false);
    }
  };

  // Clear Filters helper
  const handleClearFilters = () => {
    setStatusFilter('ALL');
    setSourceFilter('ALL');
    setDisciplineFilter('ALL');
    setConfidenceFilter('ALL');
    setSearchQuery('');
  };

  return (
    <div className="review-center-page">
      {/* 1. Header */}
      <div className="review-center-header">
        <div className="header-left">
          <div className="title-row">
            <ClipboardCheck size={22} className="review-header-icon" />
            <h1 className="review-title">Planner Review Center</h1>
            <span className="planner-control-badge">
              <Shield size={12} />
              <span>PLANNER CONTROL</span>
            </span>
          </div>
          <p className="review-subtitle">
            Resolve unmatched and uncertain field progress updates before they affect project execution.
          </p>
        </div>
        <div className="header-right">
          <button
            type="button"
            className="btn-refresh"
            onClick={() => {
              fetchSummary();
              fetchCases(casesPage);
            }}
            title="Refresh review cases"
          >
            <RefreshCw size={14} className={casesLoading ? 'spin-icon' : ''} />
            <span>Sync & Refresh</span>
          </button>
        </div>
      </div>

      {/* 2. 4 Summary Cards */}
      <div className="review-center-summary-grid">
        <div className="review-summary-card card-needs-review">
          <div className="card-top">
            <span className="card-label">Needs Review</span>
            <AlertCircle size={18} className="card-icon icon-needs-review" />
          </div>
          <div className="card-value">{summaryLoading ? '...' : summary.needs_review}</div>
          <div className="card-subtext">Unresolved field updates</div>
        </div>

        <div className="review-summary-card card-low-conf">
          <div className="card-top">
            <span className="card-label">Low Confidence</span>
            <Sparkles size={18} className="card-icon icon-low-conf" />
          </div>
          <div className="card-value">{summaryLoading ? '...' : summary.low_confidence}</div>
          <div className="card-subtext">Ambiguous AI matches</div>
        </div>

        <div className="review-summary-card card-unmatched">
          <div className="card-top">
            <span className="card-label">Unmatched</span>
            <AlertTriangle size={18} className="card-icon icon-unmatched" />
          </div>
          <div className="card-value">{summaryLoading ? '...' : summary.unmatched}</div>
          <div className="card-subtext">No activity connected</div>
        </div>

        <div className="review-summary-card card-resolved">
          <div className="card-top">
            <span className="card-label">Resolved</span>
            <CheckCircle2 size={18} className="card-icon icon-resolved" />
          </div>
          <div className="card-value">{summaryLoading ? '...' : summary.resolved + summary.applied}</div>
          <div className="card-subtext">
            {summary.applied} applied • {summary.resolved} pending apply
          </div>
        </div>
      </div>

      {/* 3. Filter Bar Card */}
      <div className="review-center-filter-card">
        <div className="filter-search-box">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            className="filter-search-input"
            placeholder="Search unresolved updates, codes, or reporters..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button
              type="button"
              className="clear-search-btn"
              onClick={() => setSearchQuery('')}
              title="Clear search"
            >
              <X size={14} />
            </button>
          )}
        </div>

        <div className="filter-controls-group">
          <div className="filter-select-wrapper">
            <label className="filter-label">Status</label>
            <select
              className="filter-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="ALL">All Statuses</option>
              <option value="NEEDS_REVIEW">Needs Review</option>
              <option value="RESOLVED">Resolved</option>
              <option value="REJECTED">Rejected</option>
              <option value="UNPLANNED">Unplanned</option>
              <option value="APPLIED">Applied</option>
            </select>
          </div>

          <div className="filter-select-wrapper">
            <label className="filter-label">Source</label>
            <select
              className="filter-select"
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
            >
              <option value="ALL">All Sources</option>
              <option value="AI_REPORT">Project AI</option>
              <option value="PROGRESS_REPORT">Progress Reports</option>
            </select>
          </div>

          <div className="filter-select-wrapper">
            <label className="filter-label">Discipline</label>
            <select
              className="filter-select"
              value={disciplineFilter}
              onChange={(e) => setDisciplineFilter(e.target.value)}
            >
              <option value="ALL">All Disciplines</option>
              {DISCIPLINES.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-select-wrapper">
            <label className="filter-label">Confidence</label>
            <select
              className="filter-select"
              value={confidenceFilter}
              onChange={(e) => setConfidenceFilter(e.target.value)}
            >
              <option value="ALL">All Confidences</option>
              <option value="HIGH">High (≥85%)</option>
              <option value="MEDIUM">Medium (65%–84%)</option>
              <option value="LOW">Low (&lt;65%)</option>
              <option value="UNMATCHED">Unmatched</option>
            </select>
          </div>

          <button
            type="button"
            className="btn-clear-filters"
            onClick={handleClearFilters}
            title="Reset all filters"
          >
            <RotateCcw size={13} />
            <span>Reset</span>
          </button>
        </div>
      </div>

      {/* 4. Main Review Queue Table Card */}
      <div className="review-center-table-card">
        <div className="table-header-row">
          <div className="table-title-group">
            <h2 className="table-heading">Review Queue</h2>
            <span className="table-count-badge">{casesTotal} items</span>
          </div>
        </div>

        {casesLoading ? (
          <div className="review-loading-box">
            <RefreshCw size={20} className="spin-icon" />
            <span>Loading review cases...</span>
          </div>
        ) : cases.length === 0 ? (
          <div className="review-empty-state">
            <CheckCircle2 size={36} className="empty-icon" />
            <h3 className="empty-title">No updates require review</h3>
            <p className="empty-desc">
              All currently submitted field updates have been resolved or filtered out.
            </p>
            {(statusFilter !== 'ALL' ||
              sourceFilter !== 'ALL' ||
              disciplineFilter !== 'ALL' ||
              confidenceFilter !== 'ALL' ||
              searchQuery) && (
              <button type="button" className="btn-secondary btn-sm" onClick={handleClearFilters}>
                Clear active filters
              </button>
            )}
          </div>
        ) : (
          <div className="table-responsive-container">
            <table className="review-queue-table">
              <thead>
                <tr>
                  <th style={{ width: '30%' }}>Field Update</th>
                  <th style={{ width: '12%' }}>Source</th>
                  <th style={{ width: '20%' }}>AI Match</th>
                  <th style={{ width: '12%' }}>Confidence</th>
                  <th style={{ width: '11%' }}>Reported Date</th>
                  <th style={{ width: '15%' }}>Review Status</th>
                  <th style={{ width: '10%', textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => {
                  const isUnmatched = !c.original_activity_code;
                  const confVal = c.original_confidence ? Math.round(c.original_confidence * 100) : 0;
                  let confBadgeClass = 'conf-low';
                  if (c.original_confidence >= 0.85) confBadgeClass = 'conf-high';
                  else if (c.original_confidence >= 0.65) confBadgeClass = 'conf-medium';

                  return (
                    <tr key={c.id} className={`queue-row ${c.decision === 'NEEDS_REVIEW' ? 'row-pending' : ''}`}>
                      <td className="col-field-update">
                        <div className="update-text" title={c.original_text}>
                          {c.original_text}
                        </div>
                        <div className="update-meta">
                          {c.discipline && <span className="meta-discipline">{c.discipline}</span>}
                          {c.reporter_name && (
                            <span className="meta-reporter">Reported by {c.reporter_name}</span>
                          )}
                        </div>
                      </td>

                      <td className="col-source">
                        {c.source_type === 'AI_REPORT' ? (
                          <span className="source-badge badge-ai-chat">
                            <Bot size={12} />
                            <span>AI CHAT</span>
                          </span>
                        ) : (
                          <span className="source-badge badge-report-import">
                            <FileSpreadsheet size={12} />
                            <span>REPORT IMPORT</span>
                          </span>
                        )}
                      </td>

                      <td className="col-ai-match">
                        {c.original_activity_code ? (
                          <div className="matched-act-box">
                            <span className="act-code font-mono">{c.original_activity_code}</span>
                            <span className="act-name" title={c.original_activity_name}>
                              {c.original_activity_name}
                            </span>
                          </div>
                        ) : (
                          <span className="unmatched-label">No activity matched</span>
                        )}
                      </td>

                      <td className="col-confidence">
                        {isUnmatched ? (
                          <span className="conf-badge conf-unmatched">UNMATCHED</span>
                        ) : (
                          <span className={`conf-badge ${confBadgeClass}`}>
                            {confVal}% {c.original_confidence >= 0.85 ? 'HIGH' : c.original_confidence >= 0.65 ? 'MED' : 'LOW'}
                          </span>
                        )}
                      </td>

                      <td className="col-date font-mono">
                        {c.reported_date || '—'}
                      </td>

                      <td className="col-status">
                        <span className={`status-badge status-${c.decision.toLowerCase()}`}>
                          {c.decision.replace('_', ' ')}
                        </span>
                        {c.decision === 'RESOLVED' && c.selected_activity_code && (
                          <div className="resolved-act-subtext font-mono">
                            ↳ {c.selected_activity_code}
                          </div>
                        )}
                      </td>

                      <td className="col-action" style={{ textAlign: 'right' }}>
                        <button
                          type="button"
                          className={c.decision === 'NEEDS_REVIEW' ? 'btn-primary btn-sm' : 'btn-secondary btn-sm'}
                          onClick={() => loadCaseDetail(c.id)}
                        >
                          {c.decision === 'NEEDS_REVIEW' ? 'Review' : 'View'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {casesTotalPages > 1 && (
          <div className="table-pagination-footer">
            <span className="page-info">
              Page {casesPage} of {casesTotalPages} ({casesTotal} total updates)
            </span>
            <div className="page-buttons">
              <button
                type="button"
                className="btn-page"
                disabled={casesPage <= 1 || casesLoading}
                onClick={() => fetchCases(casesPage - 1)}
              >
                <ChevronLeft size={14} />
                <span>Previous</span>
              </button>
              <button
                type="button"
                className="btn-page"
                disabled={casesPage >= casesTotalPages || casesLoading}
                onClick={() => fetchCases(casesPage + 1)}
              >
                <span>Next</span>
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 5. Review Detail Drawer Experience */}
      {selectedCaseId && (
        <div className="review-drawer-backdrop" onClick={closeDetailDrawer}>
          <div className="review-drawer-container" onClick={(e) => e.stopPropagation()}>
            {detailLoading ? (
              <div className="drawer-loading-box">
                <RefreshCw size={24} className="spin-icon" />
                <span>Loading case detail #{selectedCaseId}...</span>
              </div>
            ) : detailError && !caseDetail ? (
              <div className="drawer-error-box">
                <AlertCircle size={24} />
                <p>{detailError}</p>
                <button type="button" className="btn-secondary" onClick={closeDetailDrawer}>
                  Close
                </button>
              </div>
            ) : caseDetail ? (
              <>
                {/* Drawer Topbar */}
                <div className="drawer-header">
                  <div className="drawer-title-group">
                    <span className="case-id-badge font-mono">Case #{caseDetail.id}</span>
                    <span className={`status-badge status-${caseDetail.decision.toLowerCase()}`}>
                      {caseDetail.decision.replace('_', ' ')}
                    </span>
                    {caseDetail.source_type === 'AI_REPORT' ? (
                      <span className="source-badge badge-ai-chat">
                        <Bot size={12} />
                        <span>AI CHAT</span>
                      </span>
                    ) : (
                      <span className="source-badge badge-report-import">
                        <FileSpreadsheet size={12} />
                        <span>REPORT IMPORT</span>
                      </span>
                    )}
                  </div>
                  <button type="button" className="drawer-close-btn" onClick={closeDetailDrawer} title="Close drawer">
                    <X size={18} />
                  </button>
                </div>

                {/* Drawer Content */}
                <div className="drawer-body">
                  {/* Global Success / Error Messages */}
                  {actionSuccessMsg && (
                    <div className="drawer-banner banner-success">
                      <CheckCircle2 size={16} />
                      <span>{actionSuccessMsg}</span>
                    </div>
                  )}
                  {detailError && (
                    <div className="drawer-banner banner-error">
                      <AlertCircle size={16} />
                      <span>{detailError}</span>
                    </div>
                  )}

                  {/* Section 1: Original Field Update */}
                  <section className="drawer-section section-original-update">
                    <div className="section-header-row">
                      <span className="section-title">1. Original Field Update</span>
                      <span className="section-hint">Raw unmodified submission</span>
                    </div>
                    <div className="original-text-box">
                      "{caseDetail.original_text}"
                    </div>
                    <div className="original-meta-grid">
                      <div className="meta-item">
                        <span className="meta-label">Source:</span>
                        <span className="meta-val">
                          {caseDetail.source_type === 'AI_REPORT' ? 'AI Chat Reporting' : 'Batch Progress Report'}
                        </span>
                      </div>
                      <div className="meta-item">
                        <span className="meta-label">Reported By:</span>
                        <span className="meta-val">{caseDetail.reporter_name || 'Supervisor'}</span>
                      </div>
                      <div className="meta-item">
                        <span className="meta-label">Reported Date:</span>
                        <span className="meta-val font-mono">{caseDetail.reported_date || 'Today'}</span>
                      </div>
                      <div className="meta-item">
                        <span className="meta-label">Discipline:</span>
                        <span className="meta-val">{caseDetail.discipline || 'UNASSIGNED'}</span>
                      </div>
                    </div>
                  </section>

                  {/* Section 2: Extracted Execution Change */}
                  <section className="drawer-section section-extracted-change">
                    <div className="section-header-row">
                      <span className="section-title">2. Extracted Execution Intent</span>
                    </div>
                    <div className="extracted-params-grid">
                      <div className="param-item">
                        <span className="param-label">Action</span>
                        <span className="param-value param-action">
                          {caseDetail.extracted_update_type || 'PROGRESS'}
                        </span>
                      </div>
                      <div className="param-item">
                        <span className="param-label">Progress</span>
                        <span className="param-value font-mono">
                          {caseDetail.extracted_progress_percentage !== null &&
                          caseDetail.extracted_progress_percentage !== undefined
                            ? `${caseDetail.extracted_progress_percentage}%`
                            : '—'}
                        </span>
                      </div>
                      <div className="param-item">
                        <span className="param-label">Date</span>
                        <span className="param-value font-mono">{caseDetail.reported_date || '—'}</span>
                      </div>
                      <div className="param-item full-width">
                        <span className="param-label">Remarks</span>
                        <span className="param-value">{caseDetail.remarks || 'No remarks provided.'}</span>
                      </div>
                    </div>
                  </section>

                  {/* Section 3: AI Match */}
                  <section className="drawer-section section-ai-match">
                    <div className="section-header-row">
                      <span className="section-title">3. Original AI Match</span>
                    </div>
                    {caseDetail.original_activity_code ? (
                      <div className="ai-suggestion-box">
                        <div className="sugg-top">
                          <span className="act-code font-mono">{caseDetail.original_activity_code}</span>
                          <span className="act-name">{caseDetail.original_activity_name}</span>
                        </div>
                        <div className="sugg-bottom">
                          <span className="act-discipline">{caseDetail.discipline}</span>
                          <span className="sugg-conf font-mono">
                            Confidence: {Math.round((caseDetail.original_confidence || 0) * 100)}% ({caseDetail.match_status})
                          </span>
                        </div>
                      </div>
                    ) : (
                      <div className="ai-unmatched-box">
                        <AlertTriangle size={15} />
                        <span>No baseline activity was confidently matched by the AI engine.</span>
                      </div>
                    )}
                  </section>

                  {/* Section 4: Link to Schedule Activity */}
                  <section className="drawer-section section-select-activity">
                    <div className="section-header-row">
                      <span className="section-title">4. Link to Schedule Activity</span>
                      <span className="section-hint">Select a suggestion or search baseline</span>
                    </div>

                    {/* Manual Search Field */}
                    <div className="activity-search-field">
                      <Search size={15} className="search-field-icon" />
                      <input
                        type="text"
                        className="activity-search-input"
                        placeholder="Search all project activities by code, name, or discipline..."
                        value={manualSearchQuery}
                        onChange={(e) => handleManualActivitySearch(e.target.value)}
                        disabled={caseDetail.decision === 'APPLIED'}
                      />
                      {manualSearchLoading && <RefreshCw size={14} className="spin-icon search-loading-icon" />}
                    </div>

                    {/* Manual Search Results dropdown list */}
                    {manualSearchResults.length > 0 && (
                      <div className="manual-results-dropdown">
                        <div className="results-header">Search Results ({manualSearchResults.length})</div>
                        {manualSearchResults.map((act) => (
                          <div
                            key={act.id}
                            className={`result-item ${selectedActivityId === act.id ? 'active' : ''}`}
                            onClick={() => {
                              setSelectedActivityId(act.id);
                              setManualSearchResults([]);
                            }}
                          >
                            <span className="act-code font-mono">{act.activity_code}</span>
                            <span className="act-name">{act.activity_name}</span>
                            <span className="act-discipline-tag">{act.discipline}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Candidate Suggestions */}
                    <div className="candidates-list">
                      <div className="candidates-label">Suggested Matches:</div>
                      {caseDetail.candidates && caseDetail.candidates.length > 0 ? (
                        caseDetail.candidates.map((cand) => {
                          const isSelected = selectedActivityId === cand.activity_id;
                          return (
                            <div
                              key={cand.activity_id}
                              className={`candidate-card ${isSelected ? 'selected' : ''}`}
                              onClick={() => {
                                if (caseDetail.decision !== 'APPLIED') {
                                  setSelectedActivityId(cand.activity_id);
                                }
                              }}
                            >
                              <div className="card-radio">
                                <div className={`radio-dot ${isSelected ? 'checked' : ''}`} />
                              </div>
                              <div className="card-info">
                                <div className="card-top">
                                  <span className="act-code font-mono">{cand.activity_code}</span>
                                  <span className="act-name">{cand.activity_name}</span>
                                </div>
                                <div className="card-bottom">
                                  <span className="act-discipline-tag">{cand.discipline}</span>
                                  <span className="cand-conf font-mono">
                                    {Math.round(cand.confidence * 100)}% match
                                  </span>
                                  <span className="cand-status">Status: {cand.exec_status}</span>
                                </div>
                              </div>
                            </div>
                          );
                        })
                      ) : (
                        <div className="no-candidates-msg">No suggestions found. Use search above.</div>
                      )}
                    </div>

                    {/* Link Reason (Optional for link, required for reject/unplanned) */}
                    {caseDetail.decision !== 'APPLIED' && (
                      <div className="link-reason-box">
                        <label className="reason-label">Planner Note / Rationale (Optional):</label>
                        <input
                          type="text"
                          className="reason-input"
                          placeholder="e.g. Site terminology corresponds to foundation concreting..."
                          value={linkReason}
                          onChange={(e) => setLinkReason(e.target.value)}
                        />
                      </div>
                    )}
                  </section>

                  {/* Section 5: Current vs Proposed Execution Context */}
                  <section className="drawer-section section-execution-context">
                    <div className="section-header-row">
                      <span className="section-title">5. Execution Impact Preview</span>
                    </div>
                    <div className="context-comparison-grid">
                      <div className="context-column current-col">
                        <div className="col-heading">Current State</div>
                        <div className="col-body">
                          <div className="context-metric">
                            <span className="metric-label">Status:</span>
                            <span className="metric-value font-mono">
                              {caseDetail.current_execution_status || 'NOT_STARTED'}
                            </span>
                          </div>
                          <div className="context-metric">
                            <span className="metric-label">Progress:</span>
                            <span className="metric-value font-mono">
                              {caseDetail.current_progress_percentage || 0}%
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="comparison-arrow">
                        <ArrowRight size={18} />
                      </div>

                      <div className="context-column proposed-col">
                        <div className="col-heading">Proposed State</div>
                        <div className="col-body">
                          <div className="context-metric">
                            <span className="metric-label">Status:</span>
                            <span className="metric-value font-mono text-bold">
                              {caseDetail.proposed_execution_status || 'IN_PROGRESS'}
                            </span>
                          </div>
                          <div className="context-metric">
                            <span className="metric-label">Progress:</span>
                            <span className="metric-value font-mono text-bold">
                              {caseDetail.proposed_progress_percentage !== null
                                ? `${caseDetail.proposed_progress_percentage}%`
                                : '—'}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </section>

                  {/* Section 6: Validation Panel */}
                  <section className="drawer-section section-validation">
                    {caseDetail.validation_status === 'VALID' ? (
                      <div className="validation-panel panel-valid">
                        <CheckCircle2 size={18} className="val-icon" />
                        <div className="val-text">
                          <div className="val-title">Valid Execution Transition</div>
                          <div className="val-desc">
                            This update complies with Phase 5 execution state machine rules and can be applied after confirmation.
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="validation-panel panel-invalid">
                        <AlertCircle size={18} className="val-icon" />
                        <div className="val-text">
                          <div className="val-title">Cannot Apply</div>
                          <div className="val-desc">
                            {caseDetail.validation_error || 'Execution transition is invalid.'}
                          </div>
                        </div>
                      </div>
                    )}
                  </section>

                  {/* Section 7: Audit Timeline */}
                  <section className="drawer-section section-audit">
                    <div className="section-header-row">
                      <span className="section-title">Review Audit</span>
                    </div>
                    <div className="audit-timeline">
                      <div className="timeline-item">
                        <div className="dot" />
                        <div className="timeline-content">
                          <span className="time-title">Submitted</span>
                          <span className="time-desc">
                            {caseDetail.created_at ? new Date(caseDetail.created_at).toLocaleDateString() : '—'} • Reported by {caseDetail.reporter_name || 'Supervisor'}
                          </span>
                        </div>
                      </div>

                      {caseDetail.original_activity_code && (
                        <div className="timeline-item">
                          <div className="dot" />
                          <div className="timeline-content">
                            <span className="time-title">AI Suggestion</span>
                            <span className="time-desc font-mono">
                              {caseDetail.original_activity_code} ({Math.round((caseDetail.original_confidence || 0) * 100)}%)
                            </span>
                          </div>
                        </div>
                      )}

                      {caseDetail.reviewed_at && (
                        <div className="timeline-item">
                          <div className="dot" />
                          <div className="timeline-content">
                            <span className="time-title">Resolved</span>
                            <span className="time-desc">
                              {new Date(caseDetail.reviewed_at).toLocaleDateString()} • {caseDetail.reviewed_by_name || 'Planner'}
                            </span>
                            {caseDetail.selected_activity_code && (
                              <span className="time-sub font-mono">
                                Selected: {caseDetail.selected_activity_code}
                              </span>
                            )}
                            {caseDetail.review_reason && (
                              <span className="time-sub">Reason: "{caseDetail.review_reason}"</span>
                            )}
                          </div>
                        </div>
                      )}

                      {caseDetail.applied_at && (
                        <div className="timeline-item item-applied">
                          <div className="dot dot-green" />
                          <div className="timeline-content">
                            <span className="time-title text-green">Applied to Execution</span>
                            <span className="time-desc">
                              {new Date(caseDetail.applied_at).toLocaleDateString()}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  </section>
                </div>

                {/* Drawer Footer Actions */}
                <div className="drawer-footer">
                  {caseDetail.decision === 'APPLIED' ? (
                    <div className="applied-banner-footer">
                      <CheckCircle2 size={16} />
                      <span>This review case has been applied to project execution.</span>
                    </div>
                  ) : (
                    <div className="footer-action-buttons">
                      {/* Left: Reject / Unplanned */}
                      <div className="footer-left-actions">
                        <button
                          type="button"
                          className="btn-danger-outline btn-sm"
                          onClick={() => {
                            setActionReason('');
                            setActionError('');
                            setModalType('REJECT');
                          }}
                          disabled={isLinking || isProcessingAction}
                        >
                          Reject Update
                        </button>

                        <button
                          type="button"
                          className="btn-secondary btn-sm"
                          onClick={() => {
                            setActionReason('');
                            setActionError('');
                            setModalType('UNPLANNED');
                          }}
                          disabled={isLinking || isProcessingAction}
                        >
                          Mark as Unplanned
                        </button>
                      </div>

                      {/* Right: Link / Apply */}
                      <div className="footer-right-actions">
                        <button
                          type="button"
                          className="btn-secondary"
                          onClick={handleLinkActivity}
                          disabled={isLinking || !selectedActivityId || isProcessingAction}
                        >
                          {isLinking ? 'Linking...' : 'Link Activity'}
                        </button>

                        {caseDetail.decision === 'RESOLVED' && caseDetail.validation_status === 'VALID' && (
                          <button
                            type="button"
                            className="btn-primary"
                            onClick={() => {
                              setActionError('');
                              setModalType('APPLY_CONFIRM');
                            }}
                            disabled={isProcessingAction}
                          >
                            Apply Resolved Update
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}

      {/* 6. Action Modal (Reject / Unplanned / Apply Confirmation) */}
      {modalType && (
        <div className="action-modal-backdrop" onClick={() => !isProcessingAction && setModalType(null)}>
          <div className="action-modal-container" onClick={(e) => e.stopPropagation()}>
            {modalType === 'REJECT' && (
              <>
                <div className="modal-header">
                  <h3 className="modal-title">Reject Field Update</h3>
                  <button type="button" className="modal-close" onClick={() => setModalType(null)}>
                    <X size={16} />
                  </button>
                </div>
                <div className="modal-body">
                  <p className="modal-desc">
                    Rejecting this update marks it as invalid without affecting actual schedule progress.
                  </p>
                  <div className="form-group">
                    <label className="input-label required">Rejection Reason:</label>
                    <textarea
                      className="modal-textarea"
                      rows={3}
                      placeholder="e.g. Duplicate submission, incorrect site report, or not execution progress..."
                      value={actionReason}
                      onChange={(e) => setActionReason(e.target.value)}
                    />
                  </div>
                  {actionError && <div className="modal-error">{actionError}</div>}
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn-secondary" onClick={() => setModalType(null)} disabled={isProcessingAction}>
                    Cancel
                  </button>
                  <button type="button" className="btn-danger" onClick={handleRejectCase} disabled={isProcessingAction}>
                    {isProcessingAction ? 'Rejecting...' : 'Reject Update'}
                  </button>
                </div>
              </>
            )}

            {modalType === 'UNPLANNED' && (
              <>
                <div className="modal-header">
                  <h3 className="modal-title">Mark as Unplanned Work</h3>
                  <button type="button" className="modal-close" onClick={() => setModalType(null)}>
                    <X size={16} />
                  </button>
                </div>
                <div className="modal-body">
                  <p className="modal-desc">
                    Use this when the reported work is valid site activity but has no corresponding activity in the current baseline schedule.
                    The baseline schedule will remain protected and unchanged.
                  </p>
                  <div className="form-group">
                    <label className="input-label required">Reason / Description:</label>
                    <textarea
                      className="modal-textarea"
                      rows={3}
                      placeholder="e.g. Temporary weather mitigation ditching not represented in baseline schedule..."
                      value={actionReason}
                      onChange={(e) => setActionReason(e.target.value)}
                    />
                  </div>
                  {actionError && <div className="modal-error">{actionError}</div>}
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn-secondary" onClick={() => setModalType(null)} disabled={isProcessingAction}>
                    Cancel
                  </button>
                  <button type="button" className="btn-primary" onClick={handleMarkUnplanned} disabled={isProcessingAction}>
                    {isProcessingAction ? 'Saving...' : 'Mark Unplanned'}
                  </button>
                </div>
              </>
            )}

            {modalType === 'APPLY_CONFIRM' && (
              <>
                <div className="modal-header">
                  <h3 className="modal-title">Apply Progress Update?</h3>
                  <button type="button" className="modal-close" onClick={() => setModalType(null)}>
                    <X size={16} />
                  </button>
                </div>
                <div className="modal-body">
                  <p className="modal-desc">
                    This action will update the actual project execution state and create an immutable audit log.
                  </p>

                  <div className="apply-diff-card">
                    <div className="diff-item">
                      <span className="diff-label">Activity:</span>
                      <span className="diff-val font-mono">
                        {caseDetail?.selected_activity_code} — {caseDetail?.selected_activity_name}
                      </span>
                    </div>
                    <div className="diff-item">
                      <span className="diff-label">Action:</span>
                      <span className="diff-val param-action">{caseDetail?.extracted_update_type}</span>
                    </div>
                    <div className="diff-item">
                      <span className="diff-label">Status Change:</span>
                      <span className="diff-val font-mono">
                        {caseDetail?.current_execution_status} → {caseDetail?.proposed_execution_status}
                      </span>
                    </div>
                    <div className="diff-item">
                      <span className="diff-label">Progress Change:</span>
                      <span className="diff-val font-mono">
                        {caseDetail?.current_progress_percentage}% → {caseDetail?.proposed_progress_percentage}%
                      </span>
                    </div>
                  </div>

                  {actionError && <div className="modal-error">{actionError}</div>}
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn-secondary" onClick={() => setModalType(null)} disabled={isProcessingAction}>
                    Cancel
                  </button>
                  <button type="button" className="btn-primary" onClick={handleApplyUpdate} disabled={isProcessingAction}>
                    {isProcessingAction ? 'Applying...' : 'Confirm & Apply Update'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
