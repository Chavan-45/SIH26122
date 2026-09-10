import React, { useState, useEffect, useRef } from 'react';
import {
  FileText,
  Upload,
  Clipboard,
  History,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
  ArrowRight,
  Check,
  X,
  Search,
  RefreshCw,
  FileSpreadsheet,
  UserCheck,
  ShieldAlert,
  Info,
  Trash2,
  Sparkles,
  Image as ImageIcon,
  ChevronDown,
  ChevronUp,
  FileCheck,
  Layers,
} from 'lucide-react';
import {
  previewReportSpreadsheet,
  importReportSpreadsheet,
  importReportText,
  importReportDocument,
  getProgressReports,
  getProgressReport,
  reviewReportItem,
  selectReportItemActivity,
  bulkApproveReportItems,
  applyProgressReport,
  getActivities,
} from '../services/api';

/**
 * Phase 9 & Phase 13 Progress Reports Ingestion Page Component
 * Multi-format ingestion: Spreadsheets (CSV/XLSX), Pasted DPR text, PDF documents, and Scanned Site Images.
 * Scoped styling via project index.css (.pr-* selectors).
 */
export default function ProgressReportsPage({ token, project, user, assignedDiscipline }) {
  const [activeTab, setActiveTab] = useState('import'); // 'import' | 'text' | 'document' | 'history'
  const [reportsHistory, setReportsHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Active Selected Report Session state
  const [selectedReportId, setSelectedReportId] = useState(null);
  const [activeReportData, setActiveReportData] = useState(null);
  const [loadingReport, setLoadingReport] = useState(false);

  // Spreadsheet Upload State
  const [file, setFile] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [columnMapping, setColumnMapping] = useState({});
  const [uploading, setUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  // Text Report State
  const [pastedText, setPastedText] = useState('');
  const [parsingText, setParsingText] = useState(false);

  // Document Upload State (Phase 13)
  const [docFile, setDocFile] = useState(null);
  const [docUploading, setDocUploading] = useState(false);
  const [docStep, setDocStep] = useState(1);
  const [docDragging, setDocDragging] = useState(false);
  const docInputRef = useRef(null);
  const [expandedSnippets, setExpandedSnippets] = useState({});

  // Global Page Error / Notice Alert
  const [pageError, setPageError] = useState(null);
  const [pageSuccess, setPageSuccess] = useState(null);

  // Apply Confirmation Modal
  const [showApplyConfirmModal, setShowApplyConfirmModal] = useState(false);

  // Activity Picker Modal State
  const [pickerItemId, setPickerItemId] = useState(null);
  const [pickerSearch, setPickerSearch] = useState('');
  const [pickerActivities, setPickerActivities] = useState([]);
  const [loadingActivities, setLoadingActivities] = useState(false);
  const [processingItem, setProcessingItem] = useState(null);

  useEffect(() => {
    if (project?.id) {
      loadHistory();
    }
  }, [project?.id]);

  const loadHistory = async () => {
    setLoadingHistory(true);
    const res = await getProgressReports(token, project.id);
    setLoadingHistory(false);
    if (res.success) {
      setReportsHistory(res.data || []);
    }
  };

  const loadReportDetails = async (reportId) => {
    setSelectedReportId(reportId);
    setLoadingReport(true);
    const res = await getProgressReport(token, project.id, reportId);
    setLoadingReport(false);
    if (res.success) {
      setActiveReportData(res.data);
    } else {
      setPageError(res.error || 'Failed to load progress report details');
    }
  };

  // Spreadsheet File Selection & Drag-and-Drop
  const handleFileSelected = async (selectedFile) => {
    if (!selectedFile) return;

    const ext = selectedFile.name.split('.').pop().toLowerCase();
    if (!['csv', 'xlsx'].includes(ext)) {
      setPageError(`Unsupported format .${ext}. Please upload a .csv or .xlsx file.`);
      return;
    }

    setFile(selectedFile);
    setPageError(null);
    setUploading(true);

    const res = await previewReportSpreadsheet(token, project.id, selectedFile);
    setUploading(false);

    if (res.success) {
      setPreviewData(res.data);
      setColumnMapping(res.data.detected_mapping || {});
    } else {
      setPageError(res.error || 'Failed to parse spreadsheet preview');
    }
  };

  const handleSpreadsheetDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleConfirmSpreadsheetImport = async () => {
    if (!file) return;
    setUploading(true);
    setPageError(null);

    const res = await importReportSpreadsheet(token, project.id, file, columnMapping);
    setUploading(false);

    if (res.success) {
      setActiveReportData(res.data);
      setSelectedReportId(res.data.id);
      setFile(null);
      setPreviewData(null);
      loadHistory();
      setPageSuccess('Spreadsheet report parsed successfully! Review extracted items below.');
      setTimeout(() => setPageSuccess(null), 4000);
    } else {
      setPageError(res.error || 'Failed to import spreadsheet report');
    }
  };

  // Text Report Import
  const handleImportTextDPR = async (e) => {
    e.preventDefault();
    if (!pastedText.trim()) return;

    setParsingText(true);
    setPageError(null);

    const res = await importReportText(token, project.id, pastedText.trim());
    setParsingText(false);

    if (res.success) {
      setActiveReportData(res.data);
      setSelectedReportId(res.data.id);
      setPastedText('');
      loadHistory();
      setPageSuccess('Daily Site Progress Report parsed into individual work updates! Review items below.');
      setTimeout(() => setPageSuccess(null), 4000);
    } else {
      setPageError(res.error || 'Failed to parse text report');
    }
  };

  // Document & Scanned Image Import (Phase 13)
  const handleDocFileSelected = (selectedFile) => {
    if (!selectedFile) return;

    const ext = selectedFile.name.split('.').pop().toLowerCase();
    if (!['pdf', 'jpg', 'jpeg', 'png'].includes(ext)) {
      setPageError(`Unsupported file format .${ext}. Please upload a PDF, JPG, or PNG document.`);
      return;
    }

    if (selectedFile.size > 10 * 1024 * 1024) {
      setPageError(`File size (${(selectedFile.size / (1024 * 1024)).toFixed(1)} MB) exceeds maximum limit of 10 MB.`);
      return;
    }

    setDocFile(selectedFile);
    setPageError(null);
  };

  const handleDocDrop = (e) => {
    e.preventDefault();
    setDocDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleDocFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleImportDocument = async () => {
    if (!docFile) return;

    setDocUploading(true);
    setDocStep(1);
    setPageError(null);

    // Progressive step indicator
    const stepTimer = setTimeout(() => {
      setDocStep(2);
    }, 1500);

    const res = await importReportDocument(token, project.id, docFile);
    clearTimeout(stepTimer);
    setDocUploading(false);

    if (res.success) {
      setActiveReportData(res.data);
      setSelectedReportId(res.data.id);
      setDocFile(null);
      loadHistory();
      setPageSuccess(
        `Document extracted successfully (${res.data.total_items} update${res.data.total_items === 1 ? '' : 's'} identified)! Review items below before applying.`
      );
      setTimeout(() => setPageSuccess(null), 4000);
    } else {
      setPageError(res.error || 'Failed to extract updates from document');
    }
  };

  const toggleSnippet = (itemId) => {
    setExpandedSnippets((prev) => ({
      ...prev,
      [itemId]: !prev[itemId],
    }));
  };

  // Item Review Actions (Approve / Reject)
  const handleItemReview = async (itemId, action) => {
    if (!selectedReportId || processingItem) return;
    setProcessingItem(itemId);
    setPageError(null);

    const res = await reviewReportItem(token, project.id, selectedReportId, itemId, action);
    setProcessingItem(null);

    if (res.success) {
      loadReportDetails(selectedReportId);
    } else {
      setPageError(res.error || `Failed to ${action.toLowerCase()} item`);
    }
  };

  // Bulk Approve
  const handleBulkApprove = async () => {
    if (!selectedReportId) return;
    setPageError(null);
    setLoadingReport(true);

    const res = await bulkApproveReportItems(token, project.id, selectedReportId);
    setLoadingReport(false);

    if (res.success) {
      setActiveReportData(res.data);
      setPageSuccess('All valid pending items approved!');
      setTimeout(() => setPageSuccess(null), 3000);
    } else {
      setPageError(res.error || 'Bulk approval failed');
    }
  };

  // Apply Execution Updates
  const handleApplyReport = async () => {
    if (!selectedReportId) return;
    setShowApplyConfirmModal(false);
    if (user?.role !== 'SUPERVISOR') {
      setPageError('Field progress updates must be applied by an assigned Supervisor.');
      return;
    }

    setPageError(null);
    setLoadingReport(true);

    const res = await applyProgressReport(token, project.id, selectedReportId);
    setLoadingReport(false);

    if (res.success) {
      setActiveReportData(res.data);
      loadHistory();
      setPageSuccess('Approved progress updates transactionally applied to project schedule execution!');
      setTimeout(() => setPageSuccess(null), 4000);
    } else {
      setPageError(res.error || 'Failed to apply progress updates');
    }
  };

  // Activity Picker Modal
  const openActivityPicker = (itemId) => {
    setPickerItemId(itemId);
    setPickerSearch('');
    loadPickerActivities('');
  };

  const loadPickerActivities = async (searchVal = '') => {
    setLoadingActivities(true);
    const res = await getActivities(token, project.id, {
      page: 1,
      pageSize: 20,
      search: searchVal,
      discipline: assignedDiscipline || 'ALL',
    });
    setLoadingActivities(false);
    if (res.success) {
      setPickerActivities(res.data.items || []);
    }
  };

  const handleSelectActivity = async (actId) => {
    if (!pickerItemId || !selectedReportId) return;
    setPageError(null);

    const res = await selectReportItemActivity(token, project.id, selectedReportId, pickerItemId, actId);
    setPickerItemId(null);

    if (res.success) {
      loadReportDetails(selectedReportId);
    } else {
      setPageError(res.error || 'Failed to link activity');
    }
  };

  // Render Confidence Badge
  const renderConfidenceBadge = (item) => {
    if (item.match_status === 'MANUALLY_SELECTED') {
      return (
        <span className="pr-badge pr-badge-indigo">
          <Check size={11} />
          MANUAL
        </span>
      );
    }
    const pct = item.match_confidence !== null && item.match_confidence !== undefined
      ? Math.round(item.match_confidence * 100)
      : null;
    if (item.match_status === 'MATCHED_HIGH') {
      return (
        <span className="pr-badge pr-badge-green">
          <CheckCircle2 size={11} />
          {pct ? `${pct}% HIGH` : 'HIGH'}
        </span>
      );
    }
    if (item.match_status === 'MATCHED_MEDIUM') {
      return (
        <span className="pr-badge pr-badge-amber">
          <AlertTriangle size={11} />
          {pct ? `${pct}% MED` : 'MEDIUM'}
        </span>
      );
    }
    return (
      <span className="pr-badge pr-badge-red">
        <HelpCircle size={11} />
        UNMATCHED
      </span>
    );
  };

  // Render Action Badge
  const renderActionBadge = (type) => {
    const action = type || 'PROGRESS';
    let cls = 'pr-update-progress';
    if (action === 'START') cls = 'pr-update-start';
    if (action === 'COMPLETE') cls = 'pr-update-complete';
    if (action === 'ON_HOLD') cls = 'pr-update-hold';
    if (action === 'RESUME') cls = 'pr-update-resume';
    return (
      <span className={`pr-update-badge ${cls}`}>{action}</span>
    );
  };

  // Source Type Badge Helper
  const renderSourceTypeBadge = (sourceType) => {
    const s = (sourceType || '').toUpperCase();
    if (s === 'PDF') {
      return <span className="pr-badge pr-badge-rose">PDF</span>;
    }
    if (s === 'IMAGE') {
      return <span className="pr-badge pr-badge-purple">IMAGE</span>;
    }
    if (s === 'TEXT_DPR') {
      return <span className="pr-badge pr-badge-amber">TEXT DPR</span>;
    }
    return <span className="pr-badge pr-badge-slate">{s || 'FILE'}</span>;
  };

  // History status badge helper
  const historyStatusClass = (status) => {
    if (status === 'APPLIED') return 'pr-badge-green';
    if (status === 'PARTIALLY_APPLIED') return 'pr-badge-amber';
    return 'pr-badge-blue';
  };

  // Review item status badge helper
  const reviewStatusClass = (item) => {
    if (item.validation_status === 'INVALID') return 'pr-badge-red';
    if (item.review_status === 'APPLIED') return 'pr-badge-green';
    if (item.review_status === 'APPROVED') return 'pr-badge-blue';
    if (item.review_status === 'REJECTED') return 'pr-badge-slate';
    return 'pr-badge-amber';
  };

  const reviewStatusLabel = (item) => {
    if (item.validation_status === 'INVALID') return 'INVALID';
    return item.review_status;
  };

  return (
    <div className="pr-page">

      {/* ── PAGE HEADER ── */}
      <div className="pr-header-card">
        <div className="pr-header-left">
          <div className="pr-header-icon">
            <FileText size={20} />
          </div>
          <div>
            <h2 className="pr-header-title">Progress Reports</h2>
            <p className="pr-header-subtitle">
              Import and review field execution updates from spreadsheets, Daily Progress Reports, PDFs, or scanned site logs.
            </p>
          </div>
        </div>
        <span className="pr-header-badge">Field Progress Ingestion</span>
      </div>

      {/* ── GLOBAL ALERTS ── */}
      {pageError && (
        <div className="pr-alert pr-alert-error" role="alert">
          <div className="pr-alert-left">
            <ShieldAlert size={16} />
            <span>{pageError}</span>
          </div>
          <button type="button" className="pr-alert-close" onClick={() => setPageError(null)}>
            <X size={14} />
          </button>
        </div>
      )}

      {pageSuccess && (
        <div className="pr-alert pr-alert-success" role="alert">
          <div className="pr-alert-left">
            <CheckCircle2 size={16} />
            <span>{pageSuccess}</span>
          </div>
          <button type="button" className="pr-alert-close" onClick={() => setPageSuccess(null)}>
            <X size={14} />
          </button>
        </div>
      )}

      {/* ── MODE TAB SWITCHER ── */}
      {!selectedReportId && (
        <div className="pr-tabs-row">
          <button
            type="button"
            className={`pr-tab${activeTab === 'import' ? ' pr-tab-active' : ''}`}
            onClick={() => { setActiveTab('import'); setPreviewData(null); setFile(null); }}
          >
            <FileSpreadsheet size={15} />
            Spreadsheet
          </button>
          <button
            type="button"
            className={`pr-tab${activeTab === 'text' ? ' pr-tab-active' : ''}`}
            onClick={() => setActiveTab('text')}
          >
            <Clipboard size={15} />
            Paste DPR
          </button>
          <button
            type="button"
            className={`pr-tab${activeTab === 'document' ? ' pr-tab-active' : ''}`}
            onClick={() => { setActiveTab('document'); setDocFile(null); }}
          >
            <FileCheck size={15} />
            Document / Scan
          </button>
          <button
            type="button"
            className={`pr-tab${activeTab === 'history' ? ' pr-tab-active' : ''}`}
            onClick={() => { setActiveTab('history'); loadHistory(); }}
          >
            <History size={15} />
            History
            {reportsHistory.length > 0 && (
              <span className="pr-tab-count">{reportsHistory.length}</span>
            )}
          </button>
        </div>
      )}

      {/* ══════════════════════════════════════════
          SPREADSHEET TAB
         ══════════════════════════════════════════ */}
      {activeTab === 'import' && !selectedReportId && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

          {/* Upload card */}
          <div className="pr-card">
            <div>
              <h3 className="pr-card-title">Upload Progress Spreadsheet</h3>
              <p className="pr-card-subtitle">Import field execution updates from CSV or XLSX files.</p>
            </div>

            {/* State 1: no file yet — show dropzone */}
            {!file && !previewData && (
              <div
                className={`pr-dropzone${isDragging ? ' pr-drag-over' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={(e) => { e.preventDefault(); setIsDragging(false); }}
                onDrop={handleSpreadsheetDrop}
              >
                <div className="pr-dropzone-icon">
                  <Upload size={34} />
                </div>
                <p className="pr-dropzone-title">Drag &amp; drop your progress spreadsheet here</p>
                <span className="pr-dropzone-or">or</span>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv, .xlsx"
                  className="pr-file-input-hidden"
                  onChange={(e) => e.target.files && handleFileSelected(e.target.files[0])}
                />

                <button
                  type="button"
                  className="pr-browse-btn"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <FileSpreadsheet size={15} />
                  Browse Files
                </button>

                <p className="pr-dropzone-hint">CSV or XLSX &bull; Maximum file size 10 MB</p>
              </div>
            )}

            {/* State 2: file selected, awaiting preview */}
            {file && !previewData && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div className="pr-file-card">
                  <div className="pr-file-card-left">
                    <div className="pr-file-icon-box">
                      <FileSpreadsheet size={20} />
                    </div>
                    <div>
                      <div className="pr-file-name">{file.name}</div>
                      <div className="pr-file-meta">
                        {file.name.split('.').pop().toUpperCase()} &bull; {(file.size / 1024).toFixed(1)} KB
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="pr-file-remove-btn"
                    onClick={() => { setFile(null); setPreviewData(null); }}
                  >
                    <Trash2 size={13} />
                    Remove
                  </button>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <button
                    type="button"
                    className="btn-primary btn-sm"
                    onClick={() => handleFileSelected(file)}
                    disabled={uploading}
                  >
                    {uploading ? (
                      <>
                        <RefreshCw size={14} className="pr-spin" />
                        Parsing File...
                      </>
                    ) : (
                      <>
                        Preview Report
                        <ArrowRight size={14} />
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* State 3: preview loaded — show column mapping */}
            {previewData && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div className="pr-mapping-section">
                  <div className="pr-mapping-header">
                    <div className="pr-mapping-file-info">
                      <FileSpreadsheet size={16} />
                      <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                        {previewData.filename}
                      </span>
                      <span className="pr-mapping-rows-badge">{previewData.row_count} rows</span>
                    </div>
                    <button
                      type="button"
                      className="pr-file-remove-btn"
                      onClick={() => { setFile(null); setPreviewData(null); }}
                    >
                      Change File
                    </button>
                  </div>

                  <div className="pr-mapping-grid">
                    {[
                      { key: 'description', label: 'Work Description / Activity' },
                      { key: 'activity_code', label: 'Activity Code (Optional)' },
                      { key: 'progress_percentage', label: 'Progress % (Optional)' },
                      { key: 'update_type', label: 'Status / Action (Optional)' },
                      { key: 'reported_date', label: 'Reported Date (Optional)' },
                      { key: 'remarks', label: 'Remarks (Optional)' },
                    ].map(({ key, label }) => (
                      <div key={key}>
                        <label className="pr-map-label">{label}</label>
                        <select
                          className="pr-map-select"
                          value={columnMapping[key] || ''}
                          onChange={(e) => setColumnMapping({ ...columnMapping, [key]: e.target.value })}
                        >
                          <option value="">-- Select Column --</option>
                          {previewData.headers.map((h) => (
                            <option key={h} value={h}>{h}</option>
                          ))}
                        </select>
                      </div>
                    ))}
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <button
                    type="button"
                    className="btn-primary btn-sm"
                    onClick={handleConfirmSpreadsheetImport}
                    disabled={uploading}
                  >
                    {uploading ? (
                      <>
                        <RefreshCw size={14} className="pr-spin" />
                        Parsing Report...
                      </>
                    ) : (
                      <>
                        Parse &amp; Match Report Items
                        <ArrowRight size={14} />
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Info card */}
          <div className="pr-info-card">
            <div className="pr-info-heading">
              <Info size={14} />
              What can I upload?
            </div>
            <div className="pr-info-grid">
              <div className="pr-info-item">
                <span className="pr-info-item-title">Activity Code or Description</span>
                <p className="pr-info-item-desc">
                  Provide an explicit schedule code (e.g. PIP-201) or a natural work description.
                </p>
              </div>
              <div className="pr-info-item">
                <span className="pr-info-item-title">Progress &amp; Status</span>
                <p className="pr-info-item-desc">
                  Include percentage numbers (e.g. 40%) or status keywords (START, COMPLETE, ON HOLD).
                </p>
              </div>
              <div className="pr-info-item">
                <span className="pr-info-item-title">Date &amp; Remarks</span>
                <p className="pr-info-item-desc">
                  Log date and optional field remarks will be recorded in the append-only audit trail.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════
          PASTE DPR TAB
         ══════════════════════════════════════════ */}
      {activeTab === 'text' && !selectedReportId && (
        <div className="pr-card">
          <div>
            <h3 className="pr-card-title">Paste Daily Progress Report</h3>
            <p className="pr-card-subtitle">
              Paste a field report and let the system identify individual execution updates.
            </p>
          </div>

          <form onSubmit={handleImportTextDPR} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <textarea
              className="pr-dpr-textarea"
              rows={9}
              value={pastedText}
              onChange={(e) => setPastedText(e.target.value)}
              placeholder={`Date: 10 Sep 2026\n\nCivil:\nFoundation trenching 20% completed.\n\nPiping:\nPipeline fabrication reached 40%.\n\nElectrical:\nMain panel installation started today.`}
            />
            <div className="pr-dpr-footer">
              <p className="pr-dpr-hint">
                Paste one or multiple site updates. The system will separate them into reviewable activity updates.
              </p>
              <button
                type="submit"
                className="btn-primary btn-sm"
                disabled={!pastedText.trim() || parsingText}
              >
                {parsingText ? (
                  <>
                    <RefreshCw size={14} className="pr-spin" />
                    Analyzing Report...
                  </>
                ) : (
                  <>
                    <Sparkles size={14} />
                    Analyze Report
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ══════════════════════════════════════════
          PHASE 13: DOCUMENT / SCAN TAB
         ══════════════════════════════════════════ */}
      {activeTab === 'document' && !selectedReportId && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="pr-card">
            <div>
              <h3 className="pr-card-title">Document &amp; Scanned Report Ingestion</h3>
              <p className="pr-card-subtitle">
                Upload text-based or scanned PDFs, site photos, and DPR scan sheets.
              </p>
              <div className="pr-format-chips">
                <span className="pr-format-chip">
                  <FileText size={12} /> PDF (up to 20 pages)
                </span>
                <span className="pr-format-chip">
                  <ImageIcon size={12} /> JPG / PNG Photos &amp; Scans
                </span>
                <span className="pr-format-chip">
                  <Layers size={12} /> Max 10 MB
                </span>
              </div>
            </div>

            {/* State 1: No file selected yet */}
            {!docFile && (
              <div
                className={`pr-dropzone${docDragging ? ' pr-drag-over' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setDocDragging(true); }}
                onDragLeave={(e) => { e.preventDefault(); setDocDragging(false); }}
                onDrop={handleDocDrop}
              >
                <div className="pr-dropzone-icon">
                  <Upload size={34} />
                </div>
                <p className="pr-dropzone-title">Drag &amp; drop PDF or site image report here</p>
                <span className="pr-dropzone-or">or</span>

                <input
                  ref={docInputRef}
                  type="file"
                  accept=".pdf, .jpg, .jpeg, .png"
                  className="pr-file-input-hidden"
                  onChange={(e) => e.target.files && handleDocFileSelected(e.target.files[0])}
                />

                <button
                  type="button"
                  className="pr-browse-btn"
                  onClick={() => docInputRef.current?.click()}
                >
                  <FileText size={15} />
                  Browse Files
                </button>

                <p className="pr-dropzone-hint">PDF, JPG, PNG &bull; Maximum file size 10 MB &bull; PDFs up to 20 pages</p>
              </div>
            )}

            {/* State 2: File selected, awaiting extraction */}
            {docFile && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div className="pr-file-card">
                  <div className="pr-file-card-left">
                    <div className="pr-file-icon-box">
                      {docFile.name.toLowerCase().endsWith('.pdf') ? <FileText size={20} /> : <ImageIcon size={20} />}
                    </div>
                    <div>
                      <div className="pr-file-name">{docFile.name}</div>
                      <div className="pr-file-meta">
                        {docFile.name.split('.').pop().toUpperCase()} &bull; {(docFile.size / 1024).toFixed(1)} KB
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="pr-file-remove-btn"
                    onClick={() => setDocFile(null)}
                    disabled={docUploading}
                  >
                    <Trash2 size={13} />
                    Remove
                  </button>
                </div>

                {docUploading && (
                  <div className="pr-doc-steps-box">
                    <div className={`pr-doc-step-item ${docStep === 1 ? 'active' : ''}`}>
                      {docStep === 1 ? <RefreshCw size={14} className="pr-spin" /> : <CheckCircle2 size={14} color="var(--color-success)" />}
                      <span>Step 1: Reading document content and extracting text layers...</span>
                    </div>
                    <div className={`pr-doc-step-item ${docStep === 2 ? 'active' : ''}`}>
                      {docStep === 2 ? <RefreshCw size={14} className="pr-spin" /> : <Layers size={14} />}
                      <span>Step 2: Parsing structured field progress updates and linking schedule activities...</span>
                    </div>
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <button
                    type="button"
                    className="btn-primary btn-sm"
                    onClick={handleImportDocument}
                    disabled={docUploading}
                  >
                    {docUploading ? (
                      <>
                        <RefreshCw size={14} className="pr-spin" />
                        Extracting Updates...
                      </>
                    ) : (
                      <>
                        <Sparkles size={14} />
                        Extract Updates
                        <ArrowRight size={14} />
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Document Ingestion Info Card */}
          <div className="pr-info-card">
            <div className="pr-info-heading">
              <Info size={14} />
              Two-Stage Ingestion Pipeline
            </div>
            <div className="pr-info-grid">
              <div className="pr-info-item">
                <span className="pr-info-item-title">Stage 1: Native Text Extraction</span>
                <p className="pr-info-item-desc">
                  Digital PDFs are processed directly via fast text extraction with exact page provenance tracking.
                </p>
              </div>
              <div className="pr-info-item">
                <span className="pr-info-item-title">Stage 2: Multimodal Fallback</span>
                <p className="pr-info-item-desc">
                  Scanned reports, site photos, and poor-text PDFs route to Google Gemini 2.5 Flash for visual comprehension.
                </p>
              </div>
              <div className="pr-info-item">
                <span className="pr-info-item-title">Zero Silent Updates</span>
                <p className="pr-info-item-desc">
                  All extracted items require human review and explicit confirmation before applying to execution.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════
          HISTORY TAB
         ══════════════════════════════════════════ */}
      {activeTab === 'history' && !selectedReportId && (
        <div className="pr-card">
          <div>
            <h3 className="pr-card-title">Report History</h3>
            <p className="pr-card-subtitle">Previous batch progress report imports and site log sessions.</p>
          </div>

          {loadingHistory ? (
            <p className="pr-loading-text">Loading import history…</p>
          ) : reportsHistory.length === 0 ? (
            <div className="pr-empty-state">
              <FileText size={36} />
              <h4 className="pr-empty-title">No progress reports yet</h4>
              <p className="pr-empty-desc">
                Upload a spreadsheet, PDF, site image, or paste a DPR to create the first report session.
              </p>
            </div>
          ) : (
            <div className="pr-table-wrapper">
              <table className="pr-table">
                <thead>
                  <tr>
                    <th>Report ID</th>
                    <th>Source</th>
                    <th>Uploaded By</th>
                    <th>Date</th>
                    <th>Items</th>
                    <th>Status</th>
                    <th className="text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {reportsHistory.map((rep) => (
                    <tr key={rep.id}>
                      <td>
                        <span className="pr-code-badge">#{rep.id}</span>
                      </td>
                      <td>
                        {renderSourceTypeBadge(rep.source_type)}
                      </td>
                      <td style={{ fontSize: '0.8rem', fontWeight: 600 }}>{rep.uploaded_by_name}</td>
                      <td style={{ fontSize: '0.72rem', fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}>
                        {new Date(rep.created_at).toLocaleDateString()}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{rep.total_items}</td>
                      <td>
                        <span className={`pr-badge ${historyStatusClass(rep.status)}`}>{rep.status}</span>
                      </td>
                      <td className="text-right">
                        <button
                          type="button"
                          className="pr-view-btn"
                          onClick={() => loadReportDetails(rep.id)}
                        >
                          View Details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ══════════════════════════════════════════
          REPORT REVIEW SCREEN
         ══════════════════════════════════════════ */}
      {selectedReportId && activeReportData && (
        <div className="pr-card">

          {/* Review header */}
          <div className="pr-review-header">
            <button
              type="button"
              className="pr-back-btn"
              onClick={() => { setSelectedReportId(null); setActiveReportData(null); }}
            >
              ← Back to All Reports
            </button>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <div className="pr-review-title-row">
                <h3 className="pr-review-title">
                  Review Progress Report #{activeReportData.id}
                </h3>
                {renderSourceTypeBadge(activeReportData.source_type)}
                {activeReportData.page_count && (
                  <span className="pr-badge pr-badge-slate">
                    {activeReportData.page_count} {activeReportData.page_count === 1 ? 'Page' : 'Pages'}
                  </span>
                )}
                <span className={`pr-badge ${historyStatusClass(activeReportData.status)}`}>
                  {activeReportData.status}
                </span>
              </div>

              <div className="pr-review-actions-row">
                <button
                  type="button"
                  className="pr-btn-bulk-approve"
                  onClick={handleBulkApprove}
                  disabled={loadingReport || activeReportData.status === 'APPLIED'}
                >
                  <UserCheck size={14} />
                  Approve All Valid
                </button>

                {user?.role === 'SUPERVISOR' && (
                  <button
                    type="button"
                    className="pr-btn-apply"
                    onClick={() => setShowApplyConfirmModal(true)}
                    disabled={loadingReport || activeReportData.approved_items === 0 || activeReportData.status === 'APPLIED'}
                  >
                    <CheckCircle2 size={14} />
                    Apply Confirmed Updates ({activeReportData.approved_items})
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Summary stat cards */}
          <div className="pr-summary-row">
            <div className="pr-summary-cell">
              <span className="pr-summary-label">Total</span>
              <span className="pr-summary-value">{activeReportData.total_items}</span>
            </div>
            <div className="pr-summary-cell">
              <span className="pr-summary-label" style={{ color: 'var(--color-warning-text)' }}>Pending</span>
              <span className="pr-summary-value" style={{ color: 'var(--color-warning-text)' }}>{activeReportData.pending_items}</span>
            </div>
            <div className="pr-summary-cell">
              <span className="pr-summary-label" style={{ color: '#1E40AF' }}>Approved</span>
              <span className="pr-summary-value" style={{ color: '#1E40AF' }}>{activeReportData.approved_items}</span>
            </div>
            <div className="pr-summary-cell">
              <span className="pr-summary-label" style={{ color: 'var(--color-success-text)' }}>Applied</span>
              <span className="pr-summary-value" style={{ color: 'var(--color-success-text)' }}>{activeReportData.applied_items}</span>
            </div>
            <div className="pr-summary-cell">
              <span className="pr-summary-label" style={{ color: 'var(--color-danger-text)' }}>Invalid</span>
              <span className="pr-summary-value" style={{ color: 'var(--color-danger-text)' }}>{activeReportData.invalid_items}</span>
            </div>
          </div>

          {/* Review table */}
          <div className="pr-table-wrapper">
            <table className="pr-table">
              <thead>
                <tr>
                  <th>Source Update</th>
                  <th>Matched Activity</th>
                  <th>Action</th>
                  <th>Current → Proposed</th>
                  <th>Date</th>
                  <th>Confidence</th>
                  <th>Status</th>
                  <th className="text-right">Row Action</th>
                </tr>
              </thead>
              <tbody>
                {activeReportData.items.map((item) => (
                  <tr
                    key={item.id}
                    className={item.validation_status === 'INVALID' ? 'pr-row-invalid' : ''}
                  >
                    {/* Source Update with Provenance & Snippet */}
                    <td style={{ maxWidth: 240 }}>
                      <div
                        className="pr-cell-truncate"
                        style={{ fontWeight: 600 }}
                        title={item.raw_description}
                      >
                        {item.raw_description}
                      </div>

                      {/* Source Provenance Chip */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexWrap: 'wrap' }}>
                        {item.source_page && (
                          <span className="pr-provenance-tag">
                            <FileText size={10} /> Page {item.source_page}
                          </span>
                        )}
                        {activeReportData.source_type === 'IMAGE' && !item.source_page && (
                          <span className="pr-provenance-tag">
                            <ImageIcon size={10} /> Photo Scan
                          </span>
                        )}
                      </div>

                      {/* Remarks */}
                      {item.remarks && (
                        <div
                          style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', fontStyle: 'italic', marginTop: '0.2rem' }}
                          title={item.remarks}
                        >
                          {item.remarks.length > 55 ? item.remarks.slice(0, 55) + '…' : item.remarks}
                        </div>
                      )}

                      {/* Raw Extracted Text Accordion */}
                      {item.raw_extracted_text && (
                        <div>
                          <button
                            type="button"
                            className="pr-text-snippet-btn"
                            onClick={() => toggleSnippet(item.id)}
                          >
                            {expandedSnippets[item.id] ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                            {expandedSnippets[item.id] ? 'Hide raw text' : 'Show extracted text'}
                          </button>
                          {expandedSnippets[item.id] && (
                            <div className="pr-text-snippet-box">
                              {item.raw_extracted_text}
                            </div>
                          )}
                        </div>
                      )}
                    </td>

                    {/* Matched Activity */}
                    <td>
                      {item.matched_activity_code ? (
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.2rem' }}>
                            <span className="pr-code-badge">{item.matched_activity_code}</span>
                            {item.matched_discipline && (
                              <span className="pr-badge pr-badge-slate" style={{ fontSize: '0.6rem' }}>
                                {item.matched_discipline}
                              </span>
                            )}
                          </div>
                          <div
                            style={{ fontSize: '0.7rem', color: 'var(--color-text-secondary)', fontWeight: 500 }}
                            title={item.matched_activity_name}
                          >
                            {item.matched_activity_name?.length > 40
                              ? item.matched_activity_name.slice(0, 40) + '…'
                              : item.matched_activity_name}
                          </div>
                        </div>
                      ) : (
                        <span style={{ fontSize: '0.72rem', color: 'var(--color-danger-text)', fontStyle: 'italic' }}>
                          Unmatched
                        </span>
                      )}
                    </td>

                    {/* Action badge */}
                    <td>{renderActionBadge(item.extracted_update_type)}</td>

                    {/* Current → Proposed */}
                    <td>
                      <div className="pr-progress-cell">
                        <span className="pr-progress-from">{item.current_progress ?? 0}%</span>
                        <ArrowRight size={11} style={{ color: 'var(--color-text-muted)' }} />
                        <span className="pr-progress-to">{item.proposed_progress ?? 0}%</span>
                      </div>
                    </td>

                    {/* Reported Date */}
                    <td style={{ fontSize: '0.7rem', fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}>
                      {item.reported_date || 'Today'}
                    </td>

                    {/* Confidence */}
                    <td>{renderConfidenceBadge(item)}</td>

                    {/* Status */}
                    <td>
                      <span className={`pr-badge ${reviewStatusClass(item)}`} title={item.error_message || ''}>
                        {reviewStatusLabel(item)}
                      </span>
                    </td>

                    {/* Row actions */}
                    <td>
                      {item.review_status !== 'APPLIED' && (
                        <div className="pr-row-actions">
                          {item.review_status !== 'APPROVED' && item.validation_status === 'VALID' && (
                            <button
                              type="button"
                              className="pr-action-btn pr-action-approve"
                              onClick={() => handleItemReview(item.id, 'APPROVE')}
                              disabled={processingItem === item.id}
                            >
                              <Check size={11} />
                              Approve
                            </button>
                          )}

                          <button
                            type="button"
                            className="pr-action-btn pr-action-link"
                            onClick={() => openActivityPicker(item.id)}
                            title="Link to Different Activity"
                          >
                            Link
                          </button>

                          {item.review_status !== 'REJECTED' && (
                            <button
                              type="button"
                              className="pr-action-btn pr-action-reject"
                              onClick={() => handleItemReview(item.id, 'REJECT')}
                              disabled={processingItem === item.id}
                              title="Reject this item"
                            >
                              <X size={11} />
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════
          APPLY CONFIRMATION MODAL
         ══════════════════════════════════════════ */}
      {showApplyConfirmModal && (
        <div className="pr-modal-backdrop" role="dialog" aria-modal="true">
          <div className="pr-modal-dialog">
            <h4 className="pr-modal-title">Apply Progress Updates?</h4>
            <p className="pr-modal-body">
              Applying <strong>{activeReportData?.approved_items}</strong> approved update(s) will modify actual
              schedule execution data and record permanent audit logs. This action cannot be undone.
            </p>
            <div className="pr-modal-footer">
              <button
                type="button"
                className="btn-secondary btn-sm"
                onClick={() => setShowApplyConfirmModal(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="pr-btn-apply"
                onClick={handleApplyReport}
              >
                <CheckCircle2 size={14} />
                Apply Updates
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════
          ACTIVITY PICKER MODAL
         ══════════════════════════════════════════ */}
      {pickerItemId && (
        <div className="pr-modal-backdrop" role="dialog" aria-modal="true">
          <div className="pr-modal-dialog pr-modal-dialog-lg">
            <div className="pr-picker-header">
              <h4 className="pr-modal-title">Select Schedule Activity</h4>
              <button
                type="button"
                className="pr-picker-close"
                onClick={() => setPickerItemId(null)}
              >
                <X size={16} />
              </button>
            </div>

            <div className="pr-picker-search-wrap">
              <span className="pr-picker-search-icon">
                <Search size={14} />
              </span>
              <input
                type="text"
                className="pr-picker-search"
                value={pickerSearch}
                placeholder={`Search ${assignedDiscipline || ''} activities…`}
                onChange={(e) => {
                  setPickerSearch(e.target.value);
                  loadPickerActivities(e.target.value);
                }}
              />
            </div>

            <div className="pr-picker-list">
              {loadingActivities ? (
                <div className="pr-picker-empty">Loading activities…</div>
              ) : pickerActivities.length === 0 ? (
                <div className="pr-picker-empty">No matching activities found.</div>
              ) : (
                pickerActivities.map((act) => (
                  <div
                    key={act.id}
                    className="pr-picker-item"
                    onClick={() => handleSelectActivity(act.id)}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span className="pr-code-badge">{act.activity_code}</span>
                      <span className="pr-picker-item-name">{act.activity_name}</span>
                    </div>
                    <span className="pr-picker-item-disc">{act.discipline}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
