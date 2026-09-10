import React, { useState, useEffect, useCallback } from 'react';
import {
  getScheduleSyncSummary,
  previewScheduleSync,
  createScheduleExport,
  getScheduleExports,
  getScheduleExportDetail,
  downloadScheduleExport,
} from '../services/api';
import {
  RefreshCw,
  FileSpreadsheet,
  Download,
  Eye,
  CheckCircle2,
  AlertCircle,
  Clock,
  Layers,
  TrendingUp,
  Shield,
  Info,
  ChevronRight,
  X,
  FileText,
  Calendar,
  Sparkles,
  ArrowRight,
  Database,
  Filter,
} from 'lucide-react';

export default function ScheduleSyncTab({ projectId, projectCode, projectName, token, user }) {
  // Summary & metadata states
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryError, setSummaryError] = useState(null);

  // Configuration states
  const [exportMode, setExportMode] = useState('FULL_SNAPSHOT'); // 'FULL_SNAPSHOT' | 'CHANGES_ONLY'
  const [fileFormat, setFileFormat] = useState('XLSX'); // 'XLSX' | 'CSV'

  // Preview states
  const [previewData, setPreviewData] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState(null);

  // Generation & Confirmation states
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateError, setGenerateError] = useState(null);
  const [lastGeneratedExport, setLastGeneratedExport] = useState(null);

  // History states
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);
  const [selectedHistoryExport, setSelectedHistoryExport] = useState(null);
  const [historyDetailLoading, setHistoryDetailLoading] = useState(false);

  // Download loading state
  const [downloadingId, setDownloadingId] = useState(null);

  // Load summary & history
  const fetchData = useCallback(async () => {
    if (!projectId || !token) return;
    setSummaryLoading(true);
    setSummaryError(null);

    try {
      const sumRes = await getScheduleSyncSummary(token, projectId);
      if (sumRes.success && sumRes.data) {
        setSummary(sumRes.data);
        // If no previous export exists, ensure mode is FULL_SNAPSHOT
        if (!sumRes.data.has_previous_export) {
          setExportMode('FULL_SNAPSHOT');
        }
      } else {
        setSummaryError(sumRes.error || 'Failed to load sync summary');
      }
    } catch (err) {
      setSummaryError('Network error loading sync summary');
    } finally {
      setSummaryLoading(false);
    }

    // Load History
    setHistoryLoading(true);
    try {
      const histRes = await getScheduleExports(token, projectId);
      if (histRes.success && histRes.data) {
        setHistory(histRes.data);
      } else {
        setHistoryError(histRes.error || 'Failed to load export history');
      }
    } catch (err) {
      setHistoryError('Network error loading export history');
    } finally {
      setHistoryLoading(false);
    }
  }, [projectId, token]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Handle Preview
  const handlePreview = async () => {
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const res = await previewScheduleSync(token, projectId, exportMode);
      if (res.success && res.data) {
        setPreviewData(res.data);
      } else {
        setPreviewError(res.error || 'Failed to generate preview dataset');
      }
    } catch (err) {
      setPreviewError('Network error generating preview');
    } finally {
      setPreviewLoading(false);
    }
  };

  // Handle Generate Export
  const handleGenerateExport = async () => {
    setIsGenerating(true);
    setGenerateError(null);

    try {
      const res = await createScheduleExport(token, projectId, {
        exportMode,
        fileFormat,
      });

      if (res.success && res.data) {
        setLastGeneratedExport(res.data);
        setIsConfirmModalOpen(false);
        // Refresh summary and history
        fetchData();
      } else {
        setGenerateError(res.error || 'Failed to create export snapshot');
      }
    } catch (err) {
      setGenerateError('Network error creating export snapshot');
    } finally {
      setIsGenerating(false);
    }
  };

  // Handle Download (Direct from backend snapshot)
  const handleDownload = async (exportId, fileName) => {
    setDownloadingId(exportId);
    try {
      const res = await downloadScheduleExport(token, projectId, exportId, fileName);
      if (!res.success) {
        alert(res.error || 'Download failed');
      }
    } catch (err) {
      alert('Error downloading export snapshot');
    } finally {
      setDownloadingId(null);
    }
  };

  // Handle View History Detail
  const handleViewHistoryDetail = async (exportId) => {
    setHistoryDetailLoading(true);
    try {
      const res = await getScheduleExportDetail(token, projectId, exportId);
      if (res.success && res.data) {
        setSelectedHistoryExport(res.data);
      } else {
        alert(res.error || 'Failed to load export details');
      }
    } catch (err) {
      alert('Error loading export details');
    } finally {
      setHistoryDetailLoading(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  const formatTimestamp = (tsStr) => {
    if (!tsStr) return '—';
    try {
      const d = new Date(tsStr);
      return d.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return tsStr;
    }
  };

  return (
    <div className="schedule-sync-container">
      {/* Page Header */}
      <div className="schedule-sync-header">
        <div className="header-left">
          <div className="header-title-row">
            <h1 className="schedule-sync-title">Schedule Sync &amp; Export</h1>
            <span className="planner-control-pill">
              <Shield size={12} />
              <span>PLANNER CONTROL</span>
            </span>
          </div>
          <p className="schedule-sync-subtitle">
            Prepare schedule-linked actual execution data for Primavera, Microsoft Project, and PMIS integration workflows.
          </p>
        </div>

        <div className="header-actions">
          <button
            type="button"
            className="btn-secondary sync-refresh-btn"
            onClick={fetchData}
            disabled={summaryLoading || historyLoading}
          >
            <RefreshCw size={14} className={summaryLoading || historyLoading ? 'spin-icon' : ''} />
            <span>Refresh Data</span>
          </button>
        </div>
      </div>

      {/* Integration Notice Banner */}
      <div className="schedule-sync-banner">
        <div className="banner-icon-container">
          <Info size={18} />
        </div>
        <div className="banner-content">
          <h4 className="banner-title">Integration-Ready Canonical Export</h4>
          <p className="banner-desc">
            This module generates an auditable, schedule-linked actuals snapshot using <strong>Activity Code</strong> as the canonical integration key. It preserves baseline immutability and does not directly modify Primavera P6 or Microsoft Project binary schedules.
          </p>
        </div>
      </div>

      {/* Top 4 Summary Cards */}
      <div className="schedule-sync-summary-grid">
        <div className="sync-summary-card">
          <div className="card-top">
            <span className="card-label">Total Activities</span>
            <div className="card-icon-pill icon-navy">
              <Layers size={16} />
            </div>
          </div>
          <div className="card-value font-mono">
            {summaryLoading ? '—' : summary?.total_activities ?? 0}
          </div>
          <span className="card-subtext">Baseline schedule items</span>
        </div>

        <div className="sync-summary-card">
          <div className="card-top">
            <span className="card-label">With Actuals</span>
            <div className="card-icon-pill icon-blue">
              <TrendingUp size={16} />
            </div>
          </div>
          <div className="card-value font-mono">
            {summaryLoading ? '—' : summary?.activities_with_actuals ?? 0}
          </div>
          <span className="card-subtext">Started or in-progress</span>
        </div>

        <div className="sync-summary-card">
          <div className="card-top">
            <span className="card-label">Changes Since Last Export</span>
            <div className="card-icon-pill icon-amber">
              <Clock size={16} />
            </div>
          </div>
          <div className="card-value font-mono" style={{ color: (summary?.changed_since_last_export || 0) > 0 ? '#d97706' : '#1e293b' }}>
            {summaryLoading ? '—' : summary?.changed_since_last_export ?? 0}
          </div>
          <span className="card-subtext">Execution changes pending sync</span>
        </div>

        <div className="sync-summary-card">
          <div className="card-top">
            <span className="card-label">Last Export</span>
            <div className="card-icon-pill icon-green">
              <CheckCircle2 size={16} />
            </div>
          </div>
          <div className="card-value" style={{ fontSize: '1rem', fontWeight: 600, marginTop: '0.25rem' }}>
            {summaryLoading ? '—' : summary?.has_previous_export ? formatTimestamp(summary.last_export_at) : 'Never Exported'}
          </div>
          <span className="card-subtext">
            {summary?.has_previous_export ? `${summary.last_export_mode === 'FULL_SNAPSHOT' ? 'Full' : 'Changes'} • ${summary.last_export_format}` : 'Baseline sync pending'}
          </span>
        </div>
      </div>

      {/* Export Configuration Card */}
      <section className="sync-config-card">
        <div className="config-card-header">
          <div className="config-title-group">
            <h3 className="config-card-title">Create Schedule Export</h3>
            <p className="config-card-subtitle">
              Choose the export scope and target format, preview the integration dataset, and generate a snapshot.
            </p>
          </div>
        </div>

        <div className="config-form-grid">
          {/* Export Scope Selector */}
          <div className="config-field-group">
            <label className="field-label">Export Scope</label>
            <div className="segmented-selector">
              <div
                className={`segmented-option ${exportMode === 'FULL_SNAPSHOT' ? 'active' : ''}`}
                onClick={() => setExportMode('FULL_SNAPSHOT')}
              >
                <div className="option-header">
                  <Database size={15} />
                  <span className="option-title">Full Snapshot</span>
                </div>
                <p className="option-desc">
                  Export all baseline activities with their latest actual execution state.
                </p>
              </div>

              <div
                className={`segmented-option ${exportMode === 'CHANGES_ONLY' ? 'active' : ''} ${!summary?.has_previous_export ? 'disabled' : ''}`}
                onClick={() => {
                  if (summary?.has_previous_export) {
                    setExportMode('CHANGES_ONLY');
                  }
                }}
              >
                <div className="option-header">
                  <Clock size={15} />
                  <span className="option-title">Changes Since Last Export</span>
                </div>
                <p className="option-desc">
                  Export only activities whose execution state changed after the previous export.
                </p>
                {!summary?.has_previous_export && (
                  <span className="option-helper-tag">Create full snapshot first</span>
                )}
              </div>
            </div>
          </div>

          {/* File Format Selector */}
          <div className="config-field-group">
            <label className="field-label">File Format</label>
            <div className="format-selector-row">
              <div
                className={`format-option ${fileFormat === 'XLSX' ? 'active' : ''}`}
                onClick={() => setFileFormat('XLSX')}
              >
                <div className="format-header">
                  <FileSpreadsheet size={16} />
                  <span className="format-title">Microsoft Excel (.xlsx)</span>
                  <span className="format-badge">Recommended</span>
                </div>
                <p className="format-desc">
                  Structured multi-sheet workbook with formatted Actuals and Export Summary.
                </p>
              </div>

              <div
                className={`format-option ${fileFormat === 'CSV' ? 'active' : ''}`}
                onClick={() => setFileFormat('CSV')}
              >
                <div className="format-header">
                  <FileText size={16} />
                  <span className="format-title">Comma-Separated (.csv)</span>
                </div>
                <p className="format-desc">
                  Flat UTF-8 dataset for automated ETL and database pipelines.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Action Toolbar */}
        <div className="config-action-row">
          <button
            type="button"
            className="btn-primary preview-btn"
            onClick={handlePreview}
            disabled={previewLoading || summaryLoading}
          >
            {previewLoading ? (
              <>
                <RefreshCw size={15} className="spin-icon" />
                <span>Preparing Preview...</span>
              </>
            ) : (
              <>
                <Eye size={15} />
                <span>Preview Export Dataset</span>
              </>
            )}
          </button>
        </div>
      </section>

      {/* Success Notification Banner (when an export was just generated) */}
      {lastGeneratedExport && (
        <div className="export-success-card">
          <div className="success-icon-badge">
            <CheckCircle2 size={24} />
          </div>
          <div className="success-content">
            <h4 className="success-title">Export Snapshot Ready</h4>
            <p className="success-filename font-mono">{lastGeneratedExport.file_name}</p>
            <p className="success-meta">
              {lastGeneratedExport.row_count} activities exported ({lastGeneratedExport.export_mode === 'FULL_SNAPSHOT' ? 'Full Snapshot' : 'Changes Only'}) • Generated at {formatTimestamp(lastGeneratedExport.generated_at)}
            </p>
          </div>
          <div className="success-action">
            <button
              type="button"
              className="btn-primary download-success-btn"
              onClick={() => handleDownload(lastGeneratedExport.id, lastGeneratedExport.file_name)}
              disabled={downloadingId === lastGeneratedExport.id}
            >
              <Download size={15} />
              <span>{downloadingId === lastGeneratedExport.id ? 'Downloading...' : 'Download File'}</span>
            </button>
          </div>
        </div>
      )}

      {/* Preview Error */}
      {previewError && (
        <div className="sync-error-banner">
          <AlertCircle size={18} />
          <span>{previewError}</span>
        </div>
      )}

      {/* Export Preview Section */}
      {previewData && (
        <section className="sync-preview-card">
          <div className="preview-card-header">
            <div className="preview-header-left">
              <h3 className="preview-title">Export Dataset Preview</h3>
              <div className="preview-badges-row">
                <span className={`scope-badge ${previewData.export_mode === 'FULL_SNAPSHOT' ? 'scope-full' : 'scope-changes'}`}>
                  {previewData.export_mode === 'FULL_SNAPSHOT' ? 'Full Snapshot' : 'Changes Only'}
                </span>
                <span className="count-pill font-mono">
                  Rows to Export: {previewData.rows_to_export}
                </span>
                <span className="count-pill font-mono">
                  Changed Activities: {previewData.changed_activity_count}
                </span>
              </div>
            </div>

            <div className="preview-header-right">
              {previewData.rows_to_export > 0 && (
                <button
                  type="button"
                  className="btn-primary generate-export-btn"
                  onClick={() => setIsConfirmModalOpen(true)}
                >
                  <Download size={15} />
                  <span>Generate {fileFormat}</span>
                </button>
              )}
            </div>
          </div>

          {/* Designed "No Changes" Empty State */}
          {previewData.export_mode === 'CHANGES_ONLY' && previewData.rows_to_export === 0 ? (
            <div className="preview-no-changes-state">
              <div className="no-changes-icon">
                <CheckCircle2 size={36} />
              </div>
              <h4 className="no-changes-title">No Execution Changes Detected</h4>
              <p className="no-changes-desc">
                Actual field execution has not changed since the last successful snapshot (
                {previewData.previous_export_at ? formatTimestamp(previewData.previous_export_at) : 'previous export'}
                ).
              </p>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setExportMode('FULL_SNAPSHOT');
                  setTimeout(() => handlePreview(), 50);
                }}
              >
                <span>Switch to Full Snapshot</span>
              </button>
            </div>
          ) : (
            <div className="preview-table-container">
              <table className="preview-table">
                <thead>
                  <tr>
                    <th>Activity</th>
                    <th>Planned Dates</th>
                    <th>Actual Dates</th>
                    <th>Progress</th>
                    <th>Status</th>
                    <th>Variance</th>
                    <th>Change Flags</th>
                  </tr>
                </thead>
                <tbody>
                  {previewData.items.map((item) => (
                    <tr key={item.activity_code}>
                      {/* Activity */}
                      <td>
                        <div className="activity-cell">
                          <div className="activity-code-badge font-mono">{item.activity_code}</div>
                          <div className="activity-name">{item.activity_name}</div>
                          <span className={`discipline-pill discipline-${item.discipline.toLowerCase()}`}>
                            {item.discipline}
                          </span>
                        </div>
                      </td>

                      {/* Planned Dates */}
                      <td>
                        <div className="date-range-cell">
                          <span className="date-val">{formatDate(item.planned_start)}</span>
                          <span className="date-sep">→</span>
                          <span className="date-val">{formatDate(item.planned_finish)}</span>
                        </div>
                      </td>

                      {/* Actual Dates */}
                      <td>
                        <div className="actual-dates-cell">
                          <div>
                            <span className="actual-label">Start: </span>
                            <span className="date-val">{formatDate(item.actual_start)}</span>
                          </div>
                          <div>
                            <span className="actual-label">Finish: </span>
                            <span className="date-val">{formatDate(item.actual_finish)}</span>
                          </div>
                        </div>
                      </td>

                      {/* Progress */}
                      <td>
                        <div className="progress-cell">
                          <div className="progress-percent-val font-mono">{item.progress_percentage}%</div>
                          <div className="progress-mini-track">
                            <div
                              className="progress-mini-fill"
                              style={{
                                width: `${Math.min(item.progress_percentage, 100)}%`,
                                backgroundColor: item.progress_percentage === 100 ? '#16a34a' : '#0284c7',
                              }}
                            />
                          </div>
                        </div>
                      </td>

                      {/* Status */}
                      <td>
                        <span className={`status-badge-pill status-${item.execution_status.toLowerCase()}`}>
                          {item.execution_status.replace('_', ' ')}
                        </span>
                      </td>

                      {/* Variance */}
                      <td>
                        <div className="variance-cell">
                          {item.start_variance_days !== null && (
                            <span className={`variance-tag ${item.start_variance_days > 0 ? 'var-late' : item.start_variance_days < 0 ? 'var-early' : 'var-ontime'}`}>
                              Start {item.start_variance_days > 0 ? `+${item.start_variance_days}d` : item.start_variance_days < 0 ? `${item.start_variance_days}d` : 'On Plan'}
                            </span>
                          )}
                          {item.finish_variance_days !== null && (
                            <span className={`variance-tag ${item.finish_variance_days > 0 ? 'var-late' : item.finish_variance_days < 0 ? 'var-early' : 'var-ontime'}`}>
                              Finish {item.finish_variance_days > 0 ? `+${item.finish_variance_days}d` : item.finish_variance_days < 0 ? `${item.finish_variance_days}d` : 'On Plan'}
                            </span>
                          )}
                          {item.overdue_days > 0 && (
                            <span className="variance-tag var-overdue">
                              Overdue {item.overdue_days}d
                            </span>
                          )}
                          {item.start_variance_days === null && item.finish_variance_days === null && item.overdue_days === 0 && (
                            <span className="text-muted">—</span>
                          )}
                        </div>
                      </td>

                      {/* Changes */}
                      <td>
                        <div className="changes-tags-cell">
                          {item.change_flags && item.change_flags.length > 0 ? (
                            item.change_flags.map((flag, idx) => (
                              <span key={idx} className="change-flag-pill">
                                {flag.replace('_', ' ')}
                              </span>
                            ))
                          ) : (
                            <span className="no-change-tag">No Change</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* Export History Section */}
      <section className="sync-history-section">
        <div className="history-section-header">
          <div className="history-title-group">
            <h3 className="history-title">Export History &amp; Audit Trail</h3>
            <p className="history-subtitle">
              Previous schedule actuals snapshots generated for this project. Downloads reproduce the exact historical snapshot.
            </p>
          </div>
        </div>

        {historyLoading ? (
          <div className="history-loading-card">
            <RefreshCw size={20} className="spin-icon" />
            <span>Loading export history...</span>
          </div>
        ) : history.length === 0 ? (
          <div className="history-empty-card">
            <FileSpreadsheet size={40} className="empty-icon" />
            <h4 className="empty-title">No Exports Generated Yet</h4>
            <p className="empty-desc">
              Create the first full schedule snapshot above to establish the synchronization baseline.
            </p>
          </div>
        ) : (
          <div className="history-table-container">
            <table className="history-table">
              <thead>
                <tr>
                  <th>Generated At</th>
                  <th>Scope</th>
                  <th>Format</th>
                  <th>Rows</th>
                  <th>Changed</th>
                  <th>Generated By</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {history.map((exp) => (
                  <tr key={exp.id}>
                    <td>
                      <div className="history-date-cell">
                        <Calendar size={14} className="text-muted" />
                        <span className="font-mono">{formatTimestamp(exp.generated_at)}</span>
                      </div>
                    </td>

                    <td>
                      <span className={`scope-badge ${exp.export_mode === 'FULL_SNAPSHOT' ? 'scope-full' : 'scope-changes'}`}>
                        {exp.export_mode === 'FULL_SNAPSHOT' ? 'Full Snapshot' : 'Changes Only'}
                      </span>
                    </td>

                    <td>
                      <span className="format-badge-pill">{exp.file_format}</span>
                    </td>

                    <td className="font-mono">{exp.row_count}</td>
                    <td className="font-mono">{exp.changed_activity_count}</td>

                    <td>
                      <span className="user-label">{exp.exported_by_name || 'Lead Planner'}</span>
                    </td>

                    <td>
                      <span className={`status-pill-small ${exp.status === 'GENERATED' ? 'pill-green' : 'pill-red'}`}>
                        {exp.status}
                      </span>
                    </td>

                    <td>
                      <div className="history-actions-row">
                        <button
                          type="button"
                          className="btn-history-dl"
                          onClick={() => handleDownload(exp.id, exp.file_name)}
                          disabled={downloadingId === exp.id || exp.status !== 'GENERATED'}
                          title="Download snapshot file"
                        >
                          <Download size={14} />
                          <span>{downloadingId === exp.id ? '...' : 'Download'}</span>
                        </button>

                        <button
                          type="button"
                          className="btn-history-inspect"
                          onClick={() => handleViewHistoryDetail(exp.id)}
                          title="Inspect snapshot rows"
                        >
                          <Eye size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Confirmation Modal */}
      {isConfirmModalOpen && (
        <div className="sync-modal-overlay">
          <div className="sync-modal-dialog">
            <div className="modal-header">
              <h3 className="modal-title">Create Schedule Export Snapshot?</h3>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setIsConfirmModalOpen(false)}
              >
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              <p className="modal-lead">
                You are about to generate an immutable actuals export snapshot for <strong>{projectName}</strong> ({projectCode}).
              </p>

              <div className="modal-params-summary">
                <div className="param-row">
                  <span className="param-label">Export Scope:</span>
                  <span className="param-value font-mono">{exportMode === 'FULL_SNAPSHOT' ? 'Full Baseline Snapshot' : 'Changes Only'}</span>
                </div>
                <div className="param-row">
                  <span className="param-label">File Format:</span>
                  <span className="param-value font-mono">{fileFormat}</span>
                </div>
                <div className="param-row">
                  <span className="param-label">Total Rows to Export:</span>
                  <span className="param-value font-mono">{previewData?.rows_to_export ?? '—'}</span>
                </div>
              </div>

              <div className="modal-notice-box">
                <Shield size={16} />
                <span>
                  This operation creates an auditable export snapshot. Project execution and baseline schedules will <strong>not</strong> be modified.
                </span>
              </div>

              {generateError && (
                <div className="sync-error-banner" style={{ marginTop: '1rem' }}>
                  <AlertCircle size={16} />
                  <span>{generateError}</span>
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setIsConfirmModalOpen(false)}
                disabled={isGenerating}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={handleGenerateExport}
                disabled={isGenerating}
              >
                {isGenerating ? (
                  <>
                    <RefreshCw size={15} className="spin-icon" />
                    <span>Creating Snapshot...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 size={15} />
                    <span>Generate Export Snapshot</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Historical Export Detail Drawer */}
      {selectedHistoryExport && (
        <div className="sync-modal-overlay" onClick={() => setSelectedHistoryExport(null)}>
          <div className="history-detail-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <div className="drawer-title-group">
                <span className="drawer-kicker font-mono">EXPORT #{selectedHistoryExport.id}</span>
                <h3 className="drawer-title">{selectedHistoryExport.file_name || 'Schedule Export Snapshot'}</h3>
              </div>
              <button
                type="button"
                className="drawer-close-btn"
                onClick={() => setSelectedHistoryExport(null)}
              >
                <X size={18} />
              </button>
            </div>

            <div className="drawer-body">
              <div className="drawer-meta-grid">
                <div className="meta-item">
                  <span className="meta-label">Generated At</span>
                  <span className="meta-val font-mono">{formatTimestamp(selectedHistoryExport.generated_at)}</span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">Generated By</span>
                  <span className="meta-val">{selectedHistoryExport.exported_by_name || 'Lead Planner'}</span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">Scope</span>
                  <span className="meta-val">{selectedHistoryExport.export_mode}</span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">Format</span>
                  <span className="meta-val">{selectedHistoryExport.file_format}</span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">Total Rows</span>
                  <span className="meta-val font-mono">{selectedHistoryExport.row_count}</span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">Changed Activities</span>
                  <span className="meta-val font-mono">{selectedHistoryExport.changed_activity_count}</span>
                </div>
              </div>

              <div className="drawer-actions-bar">
                <button
                  type="button"
                  className="btn-primary drawer-dl-btn"
                  onClick={() => handleDownload(selectedHistoryExport.id, selectedHistoryExport.file_name)}
                  disabled={downloadingId === selectedHistoryExport.id}
                >
                  <Download size={15} />
                  <span>{downloadingId === selectedHistoryExport.id ? 'Downloading...' : 'Download This Snapshot'}</span>
                </button>
              </div>

              <h4 className="drawer-section-heading">Snapshotted Activities ({selectedHistoryExport.items?.length || 0})</h4>

              <div className="drawer-items-list">
                {selectedHistoryExport.items?.map((item) => (
                  <div key={item.activity_code} className="drawer-item-card">
                    <div className="item-card-top">
                      <span className="activity-code-badge font-mono">{item.activity_code}</span>
                      <span className={`status-badge-pill status-${item.execution_status.toLowerCase()}`}>
                        {item.execution_status.replace('_', ' ')}
                      </span>
                    </div>
                    <div className="item-card-name">{item.activity_name}</div>
                    <div className="item-card-details">
                      <span>Progress: <strong>{item.progress_percentage}%</strong></span>
                      <span>Planned: {item.planned_start} → {item.planned_finish}</span>
                      {item.actual_start && <span>Actual Start: {item.actual_start}</span>}
                      {item.actual_finish && <span>Actual Finish: {item.actual_finish}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
