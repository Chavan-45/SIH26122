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
  ChevronRight,
  FileSpreadsheet,
  Calendar,
  UserCheck,
  ShieldAlert,
  FileCheck,
  Layers,
  ArrowUpRight,
  Info,
  Trash2,
  Clock,
  Sparkles,
} from 'lucide-react';
import {
  previewReportSpreadsheet,
  importReportSpreadsheet,
  importReportText,
  getProgressReports,
  getProgressReport,
  reviewReportItem,
  selectReportItemActivity,
  bulkApproveReportItems,
  applyProgressReport,
  getActivities,
} from '../services/api';

/**
 * Phase 9 Progress Reports Ingestion Page Component
 * Polished Enterprise PMIS Visual Redesign
 */
export default function ProgressReportsPage({ token, project, user, assignedDiscipline }) {
  const [activeTab, setActiveTab] = useState('import'); // 'import' | 'text' | 'history'
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

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
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
        <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 inline-flex items-center gap-1">
          <Check size={11} />
          MANUAL
        </span>
      );
    }
    const pct = item.match_confidence !== null && item.match_confidence !== undefined ? Math.round(item.match_confidence * 100) : null;
    if (item.match_status === 'MATCHED_HIGH') {
      return (
        <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 inline-flex items-center gap-1">
          <CheckCircle2 size={11} />
          {pct ? `${pct}% HIGH` : 'HIGH'}
        </span>
      );
    }
    if (item.match_status === 'MATCHED_MEDIUM') {
      return (
        <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200 inline-flex items-center gap-1">
          <AlertTriangle size={11} />
          {pct ? `${pct}% MEDIUM` : 'MEDIUM'}
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200 inline-flex items-center gap-1">
        <HelpCircle size={11} />
        UNMATCHED
      </span>
    );
  };

  // Render Action Badge
  const renderActionBadge = (type) => {
    const action = type || 'PROGRESS';
    let styles = 'bg-slate-100 text-slate-700 border-slate-200';
    if (action === 'START') styles = 'bg-blue-50 text-blue-700 border-blue-200';
    if (action === 'PROGRESS') styles = 'bg-amber-50 text-amber-800 border-amber-200';
    if (action === 'COMPLETE') styles = 'bg-emerald-50 text-emerald-700 border-emerald-200';
    if (action === 'ON_HOLD') styles = 'bg-purple-50 text-purple-700 border-purple-200';
    if (action === 'RESUME') styles = 'bg-indigo-50 text-indigo-700 border-indigo-200';

    return (
      <span className={`px-2 py-0.5 rounded text-[11px] font-bold border tracking-wide uppercase inline-block ${styles}`}>
        {action}
      </span>
    );
  };

  return (
    <div className="progress-reports-page space-y-6">
      {/* 1. PAGE HEADER BAR */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="p-2.5 bg-slate-100 text-slate-800 rounded-lg border border-slate-200 mt-0.5">
            <FileText size={20} className="text-slate-800" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">Progress Reports</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Import and review field execution updates from spreadsheets or Daily Progress Reports.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-[10px] font-extrabold uppercase bg-slate-100 text-slate-700 px-3 py-1.5 rounded-md border border-slate-200 font-mono tracking-wider">
            FIELD PROGRESS
          </span>
        </div>
      </div>

      {/* GLOBAL ALERTS */}
      {pageError && (
        <div className="bg-rose-50 border border-rose-200 text-rose-800 text-xs px-4 py-3 rounded-lg flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2">
            <ShieldAlert size={16} className="text-rose-600 flex-shrink-0" />
            <span>{pageError}</span>
          </div>
          <button type="button" onClick={() => setPageError(null)} className="text-rose-500 hover:text-rose-800">
            <X size={14} />
          </button>
        </div>
      )}

      {pageSuccess && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs px-4 py-3 rounded-lg flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={16} className="text-emerald-600 flex-shrink-0" />
            <span>{pageSuccess}</span>
          </div>
          <button type="button" onClick={() => setPageSuccess(null)} className="text-emerald-500 hover:text-emerald-800">
            <X size={14} />
          </button>
        </div>
      )}

      {/* 2. TOP MODE SEGMENTED TAB SWITCHER */}
      {!selectedReportId && (
        <div className="flex items-center p-1 bg-slate-200/80 rounded-lg border border-slate-300 w-fit">
          <button
            type="button"
            onClick={() => { setActiveTab('import'); setPreviewData(null); setFile(null); }}
            className={`px-4 py-2 rounded-md text-xs font-semibold flex items-center gap-2 transition-all ${
              activeTab === 'import'
                ? 'bg-slate-900 text-white shadow-sm font-bold'
                : 'text-slate-700 hover:text-slate-900 hover:bg-slate-100/50'
            }`}
          >
            <FileSpreadsheet size={16} />
            <span>Spreadsheet</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('text')}
            className={`px-4 py-2 rounded-md text-xs font-semibold flex items-center gap-2 transition-all ${
              activeTab === 'text'
                ? 'bg-slate-900 text-white shadow-sm font-bold'
                : 'text-slate-700 hover:text-slate-900 hover:bg-slate-100/50'
            }`}
          >
            <Clipboard size={16} />
            <span>Paste DPR</span>
          </button>
          <button
            type="button"
            onClick={() => { setActiveTab('history'); loadHistory(); }}
            className={`px-4 py-2 rounded-md text-xs font-semibold flex items-center gap-2 transition-all ${
              activeTab === 'history'
                ? 'bg-slate-900 text-white shadow-sm font-bold'
                : 'text-slate-700 hover:text-slate-900 hover:bg-slate-100/50'
            }`}
          >
            <History size={16} />
            <span>History</span>
            {reportsHistory.length > 0 && (
              <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                activeTab === 'history' ? 'bg-slate-700 text-white' : 'bg-slate-300 text-slate-800'
              }`}>
                {reportsHistory.length}
              </span>
            )}
          </button>
        </div>
      )}

      {/* 3. SPREADSHEET TAB MAIN CARD */}
      {activeTab === 'import' && !selectedReportId && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-6">
            <div>
              <h3 className="font-bold text-slate-900 text-base">Upload Progress Spreadsheet</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Import field execution updates from CSV or XLSX files.
              </p>
            </div>

            {!file && !previewData ? (
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-xl p-8 text-center transition-all bg-slate-50/70 flex flex-col items-center justify-center min-h-[190px] ${
                  isDragging ? 'border-slate-800 bg-blue-50/40' : 'border-slate-300 hover:border-slate-400'
                }`}
              >
                <Upload size={32} className="text-slate-700 mb-3" />
                <p className="text-sm font-semibold text-slate-800">Drag &amp; drop your progress report here</p>
                <span className="text-xs text-slate-400 my-1 font-medium">or</span>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv, .xlsx"
                  onChange={(e) => e.target.files && handleFileSelected(e.target.files[0])}
                  className="hidden"
                />

                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="mt-1 px-4 py-2.5 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-semibold shadow-sm inline-flex items-center gap-2 transition-all"
                >
                  <FileSpreadsheet size={15} />
                  <span>Browse Files</span>
                </button>

                <p className="text-[11px] text-slate-500 mt-4 font-medium">
                  CSV or XLSX • Maximum file size 10 MB
                </p>
              </div>
            ) : file && !previewData ? (
              /* Selected File Details Box */
              <div className="bg-slate-50 rounded-xl border border-slate-200 p-5 space-y-4">
                <div className="flex items-center justify-between bg-white p-3.5 rounded-lg border border-slate-200">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 bg-slate-100 text-slate-800 rounded-lg">
                      <FileSpreadsheet size={20} />
                    </div>
                    <div>
                      <span className="font-bold text-xs text-slate-900 block">{file.name}</span>
                      <span className="text-[11px] text-slate-500 font-medium">
                        {file.name.split('.').pop().toUpperCase()} • {(file.size / 1024).toFixed(1)} KB
                      </span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => { setFile(null); setPreviewData(null); }}
                    className="text-xs text-slate-500 hover:text-slate-800 font-medium hover:underline flex items-center gap-1"
                  >
                    <Trash2 size={13} />
                    <span>Remove</span>
                  </button>
                </div>

                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => handleFileSelected(file)}
                    disabled={uploading}
                    className="px-5 py-2.5 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-bold flex items-center gap-2 shadow-sm transition-all disabled:opacity-50"
                  >
                    {uploading ? (
                      <>
                        <RefreshCw size={14} className="animate-spin" />
                        <span>Parsing File...</span>
                      </>
                    ) : (
                      <>
                        <span>Preview Report</span>
                        <ArrowRight size={14} />
                      </>
                    )}
                  </button>
                </div>
              </div>
            ) : (
              /* Column Mapping & Preview State */
              <div className="space-y-6">
                <div className="bg-slate-50 p-5 rounded-xl border border-slate-200 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                    <div className="flex items-center gap-2">
                      <FileSpreadsheet size={18} className="text-slate-800" />
                      <span className="font-bold text-xs text-slate-900">{previewData.filename}</span>
                      <span className="text-[11px] bg-slate-200 text-slate-800 px-2 py-0.5 rounded-full font-mono font-bold">
                        {previewData.row_count} rows
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => { setFile(null); setPreviewData(null); }}
                      className="text-xs text-slate-500 hover:text-slate-800 font-medium hover:underline"
                    >
                      Change File
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-[11px] font-bold text-slate-700 mb-1">Work Description / Activity</label>
                      <select
                        value={columnMapping.description || ''}
                        onChange={(e) => setColumnMapping({ ...columnMapping, description: e.target.value })}
                        className="w-full text-xs p-2 rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-slate-900 outline-none"
                      >
                        <option value="">-- Select Column --</option>
                        {previewData.headers.map((h) => (
                          <option key={h} value={h}>{h}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-bold text-slate-700 mb-1">Activity Code (Optional)</label>
                      <select
                        value={columnMapping.activity_code || ''}
                        onChange={(e) => setColumnMapping({ ...columnMapping, activity_code: e.target.value })}
                        className="w-full text-xs p-2 rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-slate-900 outline-none"
                      >
                        <option value="">-- Select Column --</option>
                        {previewData.headers.map((h) => (
                          <option key={h} value={h}>{h}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-bold text-slate-700 mb-1">Progress % (Optional)</label>
                      <select
                        value={columnMapping.progress_percentage || ''}
                        onChange={(e) => setColumnMapping({ ...columnMapping, progress_percentage: e.target.value })}
                        className="w-full text-xs p-2 rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-slate-900 outline-none"
                      >
                        <option value="">-- Select Column --</option>
                        {previewData.headers.map((h) => (
                          <option key={h} value={h}>{h}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-bold text-slate-700 mb-1">Status / Action (Optional)</label>
                      <select
                        value={columnMapping.update_type || ''}
                        onChange={(e) => setColumnMapping({ ...columnMapping, update_type: e.target.value })}
                        className="w-full text-xs p-2 rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-slate-900 outline-none"
                      >
                        <option value="">-- Select Column --</option>
                        {previewData.headers.map((h) => (
                          <option key={h} value={h}>{h}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-bold text-slate-700 mb-1">Reported Date (Optional)</label>
                      <select
                        value={columnMapping.reported_date || ''}
                        onChange={(e) => setColumnMapping({ ...columnMapping, reported_date: e.target.value })}
                        className="w-full text-xs p-2 rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-slate-900 outline-none"
                      >
                        <option value="">-- Select Column --</option>
                        {previewData.headers.map((h) => (
                          <option key={h} value={h}>{h}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-bold text-slate-700 mb-1">Remarks (Optional)</label>
                      <select
                        value={columnMapping.remarks || ''}
                        onChange={(e) => setColumnMapping({ ...columnMapping, remarks: e.target.value })}
                        className="w-full text-xs p-2 rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-slate-900 outline-none"
                      >
                        <option value="">-- Select Column --</option>
                        {previewData.headers.map((h) => (
                          <option key={h} value={h}>{h}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={handleConfirmSpreadsheetImport}
                    disabled={uploading}
                    className="px-5 py-2.5 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-bold flex items-center gap-2 shadow-sm transition-all disabled:opacity-50"
                  >
                    {uploading ? (
                      <>
                        <RefreshCw size={14} className="animate-spin" />
                        <span>Parsing Report...</span>
                      </>
                    ) : (
                      <>
                        <span>Parse &amp; Match Report Items</span>
                        <ArrowRight size={14} />
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Secondary Info Section: "What can I upload?" */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
            <h4 className="text-xs font-bold text-slate-800 mb-3 flex items-center gap-1.5">
              <Info size={14} className="text-slate-600" />
              <span>What can I upload?</span>
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-slate-600">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/80">
                <span className="font-bold text-slate-900 block mb-1">Activity Code or Description</span>
                <p className="text-[11px] text-slate-500">Provide an explicit schedule code (e.g. PIP-201) or a natural work description.</p>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/80">
                <span className="font-bold text-slate-900 block mb-1">Progress &amp; Status</span>
                <p className="text-[11px] text-slate-500">Include percentage numbers (e.g. 40%) or status keywords (START, COMPLETE, ON HOLD).</p>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/80">
                <span className="font-bold text-slate-900 block mb-1">Date &amp; Remarks</span>
                <p className="text-[11px] text-slate-500">Log date and optional field remarks will be recorded in the append-only audit trail.</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 4. PASTE DPR TAB MAIN CARD */}
      {activeTab === 'text' && !selectedReportId && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">
          <div>
            <h3 className="font-bold text-slate-900 text-base">Paste Daily Progress Report</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Paste a field report and let the system identify individual execution updates.
            </p>
          </div>

          <form onSubmit={handleImportTextDPR} className="space-y-4">
            <textarea
              rows={9}
              value={pastedText}
              onChange={(e) => setPastedText(e.target.value)}
              placeholder={`Date: 10 Sep 2026

Civil:
Foundation trenching 20% completed.

Piping:
Pipeline fabrication reached 40%.

Electrical:
Main panel installation started today.`}
              className="w-full text-xs font-mono p-4 rounded-xl border border-slate-300 focus:ring-2 focus:ring-slate-900 outline-none leading-relaxed text-slate-800"
            />
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <p className="text-[11px] text-slate-500">
                Paste one or multiple site updates. The system will separate them into reviewable activity updates.
              </p>
              <button
                type="submit"
                disabled={!pastedText.trim() || parsingText}
                className="px-5 py-2.5 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-bold flex items-center justify-center gap-2 shadow-sm transition-all disabled:opacity-50"
              >
                {parsingText ? (
                  <>
                    <RefreshCw size={14} className="animate-spin" />
                    <span>Analyzing Report...</span>
                  </>
                ) : (
                  <>
                    <Sparkles size={14} />
                    <span>Analyze Report</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* 5. HISTORY TAB TABLE & DESIGNED EMPTY STATE */}
      {activeTab === 'history' && !selectedReportId && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">
          <div>
            <h3 className="font-bold text-slate-900 text-base">Report History</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Previous batch progress report imports and site log sessions.
            </p>
          </div>

          {loadingHistory ? (
            <div className="text-center py-12 text-xs text-slate-500">Loading import history...</div>
          ) : reportsHistory.length === 0 ? (
            /* Designed Empty State */
            <div className="text-center py-12 px-4 bg-slate-50/60 border border-dashed border-slate-300 rounded-xl space-y-2">
              <FileText size={36} className="mx-auto text-slate-400" />
              <h4 className="font-bold text-slate-800 text-sm">No progress reports yet</h4>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Upload a spreadsheet or paste a Daily Progress Report to create the first report session.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto border border-slate-200 rounded-xl">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-100 text-slate-600 text-[11px] uppercase tracking-wider border-b border-slate-200">
                    <th className="py-3 px-4 font-bold">Report ID</th>
                    <th className="py-3 px-4 font-bold">Source</th>
                    <th className="py-3 px-4 font-bold">Uploaded By</th>
                    <th className="py-3 px-4 font-bold">Date</th>
                    <th className="py-3 px-4 font-bold">Items</th>
                    <th className="py-3 px-4 font-bold">Status</th>
                    <th className="py-3 px-4 font-bold text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs">
                  {reportsHistory.map((rep) => (
                    <tr key={rep.id} className="hover:bg-slate-50 transition-all">
                      <td className="py-3 px-4 font-bold text-slate-900 font-mono">
                        #{rep.id}
                      </td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                          {rep.source_type}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-medium text-slate-800">
                        {rep.uploaded_by_name}
                      </td>
                      <td className="py-3 px-4 text-slate-500 font-mono text-[11px]">
                        {new Date(rep.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-4 font-mono font-bold text-slate-800">
                        {rep.total_items}
                      </td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                          rep.status === 'APPLIED' ? 'bg-emerald-100 text-emerald-800' :
                          rep.status === 'PARTIALLY_APPLIED' ? 'bg-amber-100 text-amber-800' :
                          'bg-blue-100 text-blue-800'
                        }`}>
                          {rep.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          type="button"
                          onClick={() => loadReportDetails(rep.id)}
                          className="px-3 py-1 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded font-semibold text-[11px] transition-all"
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

      {/* 6. REPORT REVIEW SCREEN & TABLE */}
      {selectedReportId && activeReportData && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-6">
          {/* Review Header */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-4">
            <div>
              <button
                type="button"
                onClick={() => { setSelectedReportId(null); setActiveReportData(null); }}
                className="text-xs text-slate-600 hover:text-slate-900 font-semibold mb-1 block"
              >
                ← Back to All Reports
              </button>
              <h3 className="font-bold text-slate-900 text-lg flex items-center gap-2">
                <span>Review Progress Report #{activeReportData.id}</span>
                <span className="text-xs font-semibold bg-slate-100 px-2.5 py-0.5 rounded text-slate-700 border border-slate-200">
                  {activeReportData.source_type}
                </span>
                <span className={`text-xs font-bold px-2.5 py-0.5 rounded ${
                  activeReportData.status === 'APPLIED' ? 'bg-emerald-100 text-emerald-800' :
                  activeReportData.status === 'PARTIALLY_APPLIED' ? 'bg-amber-100 text-amber-800' :
                  'bg-blue-100 text-blue-800'
                }`}>
                  {activeReportData.status}
                </span>
              </h3>
            </div>

            {/* Action Bar */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleBulkApprove}
                disabled={loadingReport || activeReportData.status === 'APPLIED'}
                className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all disabled:opacity-50"
              >
                <UserCheck size={14} />
                <span>Approve All Valid</span>
              </button>

              {user?.role === 'SUPERVISOR' && (
                <button
                  type="button"
                  onClick={() => setShowApplyConfirmModal(true)}
                  disabled={loadingReport || activeReportData.approved_items === 0 || activeReportData.status === 'APPLIED'}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all shadow-sm disabled:opacity-50"
                >
                  <CheckCircle2 size={14} />
                  <span>Apply Confirmed Updates ({activeReportData.approved_items})</span>
                </button>
              )}
            </div>
          </div>

          {/* Compact Summary Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 bg-slate-50 p-3 rounded-lg border border-slate-200 text-center">
            <div>
              <span className="block text-[11px] text-slate-500 font-semibold">Total Updates</span>
              <span className="font-bold text-slate-900 text-sm">{activeReportData.total_items}</span>
            </div>
            <div>
              <span className="block text-[11px] text-amber-700 font-semibold">Needs Review</span>
              <span className="font-bold text-amber-900 text-sm">{activeReportData.pending_items}</span>
            </div>
            <div>
              <span className="block text-[11px] text-blue-700 font-semibold">Approved</span>
              <span className="font-bold text-blue-900 text-sm">{activeReportData.approved_items}</span>
            </div>
            <div>
              <span className="block text-[11px] text-emerald-700 font-semibold">Applied</span>
              <span className="font-bold text-emerald-900 text-sm">{activeReportData.applied_items}</span>
            </div>
            <div>
              <span className="block text-[11px] text-rose-700 font-semibold">Invalid</span>
              <span className="font-bold text-rose-900 text-sm">{activeReportData.invalid_items}</span>
            </div>
          </div>

          {/* Review Table */}
          <div className="overflow-x-auto border border-slate-200 rounded-xl">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-100 text-slate-600 text-[11px] uppercase tracking-wider border-b border-slate-200">
                  <th className="py-3 px-4 font-bold">Source Update</th>
                  <th className="py-3 px-4 font-bold">Matched Schedule Activity</th>
                  <th className="py-3 px-4 font-bold">Action</th>
                  <th className="py-3 px-4 font-bold">Current → Proposed</th>
                  <th className="py-3 px-4 font-bold">Reported Date</th>
                  <th className="py-3 px-4 font-bold">Confidence</th>
                  <th className="py-3 px-4 font-bold">Status</th>
                  <th className="py-3 px-4 font-bold text-right">Row Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {activeReportData.items.map((item) => (
                  <tr key={item.id} className={`hover:bg-slate-50 ${item.validation_status === 'INVALID' ? 'bg-rose-50/50' : ''}`}>
                    {/* Source Update */}
                    <td className="py-3 px-4 max-w-[220px]">
                      <div className="font-semibold text-slate-900 truncate" title={item.raw_description}>
                        {item.raw_description}
                      </div>
                      {item.remarks && (
                        <div className="text-[11px] text-slate-500 italic truncate">{item.remarks}</div>
                      )}
                    </td>

                    {/* Matched Activity */}
                    <td className="py-3 px-4">
                      {item.matched_activity_code ? (
                        <div>
                          <div className="flex items-center gap-1.5 mb-0.5">
                            <span className="px-1.5 py-0.5 rounded bg-slate-200 font-mono text-[11px] font-bold text-slate-800">
                              {item.matched_activity_code}
                            </span>
                            {item.matched_discipline && (
                              <span className="text-[10px] font-extrabold uppercase px-1.5 py-0.2 rounded bg-slate-100 text-slate-600 border border-slate-200">
                                {item.matched_discipline}
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] text-slate-700 font-medium truncate max-w-[180px]" title={item.matched_activity_name}>
                            {item.matched_activity_name}
                          </div>
                        </div>
                      ) : (
                        <span className="text-rose-600 font-medium italic text-[11px]">Unmatched activity</span>
                      )}
                    </td>

                    {/* Action */}
                    <td className="py-3 px-4">
                      {renderActionBadge(item.extracted_update_type)}
                    </td>

                    {/* Current -> Proposed */}
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1 font-mono text-[11px]">
                        <span className="text-slate-500">{item.current_progress ?? 0}%</span>
                        <ArrowRight size={11} className="text-slate-400" />
                        <span className="font-bold text-emerald-700">{item.proposed_progress ?? 0}%</span>
                      </div>
                    </td>

                    {/* Reported Date */}
                    <td className="py-3 px-4 text-slate-600 text-[11px] font-mono">
                      {item.reported_date || 'Today'}
                    </td>

                    {/* Confidence */}
                    <td className="py-3 px-4">
                      {renderConfidenceBadge(item)}
                    </td>

                    {/* Status */}
                    <td className="py-3 px-4">
                      {item.validation_status === 'INVALID' ? (
                        <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-rose-100 text-rose-800 border border-rose-200 inline-block" title={item.error_message}>
                          INVALID
                        </span>
                      ) : (
                        <span className={`px-2 py-0.5 rounded text-[11px] font-bold inline-block ${
                          item.review_status === 'APPLIED' ? 'bg-emerald-100 text-emerald-800' :
                          item.review_status === 'APPROVED' ? 'bg-blue-100 text-blue-800' :
                          item.review_status === 'REJECTED' ? 'bg-slate-200 text-slate-700' :
                          'bg-amber-100 text-amber-900'
                        }`}>
                          {item.review_status}
                        </span>
                      )}
                    </td>

                    {/* Actions */}
                    <td className="py-3 px-4 text-right">
                      {item.review_status !== 'APPLIED' && (
                        <div className="flex items-center justify-end gap-1.5">
                          {item.review_status !== 'APPROVED' && item.validation_status === 'VALID' && (
                            <button
                              type="button"
                              onClick={() => handleItemReview(item.id, 'APPROVE')}
                              disabled={processingItem === item.id}
                              className="px-2.5 py-1 bg-slate-900 hover:bg-slate-800 text-white rounded text-[11px] font-bold flex items-center gap-1 transition-all"
                            >
                              <Check size={11} />
                              <span>Approve</span>
                            </button>
                          )}

                          <button
                            type="button"
                            onClick={() => openActivityPicker(item.id)}
                            className="px-2 py-1 bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-300 rounded text-[11px] font-semibold transition-all"
                            title="Choose Different Activity"
                          >
                            Link
                          </button>

                          {item.review_status !== 'REJECTED' && (
                            <button
                              type="button"
                              onClick={() => handleItemReview(item.id, 'REJECT')}
                              disabled={processingItem === item.id}
                              className="px-2 py-1 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded text-[11px] font-semibold transition-all"
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

      {/* APPLY CONFIRMATION MODAL */}
      {showApplyConfirmModal && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 w-full max-w-md p-6 space-y-4">
            <h4 className="font-bold text-slate-900 text-base">Apply Progress Updates?</h4>
            <p className="text-xs text-slate-600 leading-relaxed">
              Applying <strong>{activeReportData?.approved_items}</strong> approved update(s) will modify actual schedule execution data and record permanent audit logs.
            </p>
            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setShowApplyConfirmModal(false)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleApplyReport}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold shadow-sm"
              >
                Apply Updates
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ACTIVITY PICKER MODAL */}
      {pickerItemId && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 w-full max-w-lg p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h4 className="font-bold text-slate-800 text-sm">Select Schedule Activity</h4>
              <button type="button" onClick={() => setPickerItemId(null)} className="text-slate-400 hover:text-slate-700">
                <X size={16} />
              </button>
            </div>

            <div className="relative">
              <Search className="absolute left-3 top-2.5 text-slate-400" size={14} />
              <input
                type="text"
                value={pickerSearch}
                onChange={(e) => {
                  setPickerSearch(e.target.value);
                  loadPickerActivities(e.target.value);
                }}
                placeholder={`Search ${assignedDiscipline || ''} activities...`}
                className="w-full text-xs pl-9 pr-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-slate-900 outline-none"
              />
            </div>

            <div className="max-h-60 overflow-y-auto divide-y divide-slate-100 border border-slate-200 rounded-lg">
              {loadingActivities ? (
                <div className="p-4 text-center text-xs text-slate-500">Loading activities...</div>
              ) : pickerActivities.length === 0 ? (
                <div className="p-4 text-center text-xs text-slate-500">No matching activities found.</div>
              ) : (
                pickerActivities.map((act) => (
                  <div
                    key={act.id}
                    onClick={() => handleSelectActivity(act.id)}
                    className="p-2.5 hover:bg-slate-50 cursor-pointer flex items-center justify-between transition-all"
                  >
                    <div>
                      <span className="px-1.5 py-0.5 rounded bg-slate-200 font-mono text-[10px] font-bold text-slate-800 mr-2">
                        {act.activity_code}
                      </span>
                      <span className="text-xs text-slate-800 font-medium">{act.activity_name}</span>
                    </div>
                    <span className="text-[10px] font-bold text-slate-500">{act.discipline}</span>
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
