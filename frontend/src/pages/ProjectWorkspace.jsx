import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  getProject,
  updateProject,
  getProjectMembers,
  addProjectMember,
  removeProjectMember,
  getSupervisors,
  getScheduleStatus,
  getActivities,
  getActivity,
  previewSchedule,
  importSchedule,
  reportActivityProgress,
  getActivityExecution,
  getActivityProgressHistory,
  getExecutionSummary,
} from '../services/api';
import Navbar from '../components/Navbar';
import DashboardTab from '../components/DashboardTab';
import ProjectAITab from '../components/ProjectAITab';
import ProgressReportsPage from './ProgressReportsPage';
import PlannerReviewCenterTab from '../components/PlannerReviewCenterTab';
import ScheduleSyncTab from '../components/ScheduleSyncTab';
import AnalyticsTab from '../components/AnalyticsTab';
import ProjectMemoryTab from '../components/ProjectMemoryTab';
import {
  Building2,
  Calendar,
  MapPin,
  Tag,
  Clock,
  Users,
  UserPlus,
  Trash2,
  Edit3,
  ArrowLeft,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Shield,
  Briefcase,
  ClipboardCheck,
  X,
  FileSpreadsheet,
  Upload,
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  ListFilter,
  Info,
  Check,
  AlertTriangle,
  Layers,
  Play,
  Pause,
  RotateCcw,
  CheckCircle,
  TrendingUp,
  BarChart3,
  History,
  Bot,
} from 'lucide-react';


const DISCIPLINES = [
  { value: 'CIVIL', label: 'Civil Engineering' },
  { value: 'PIPING', label: 'Piping & Layout' },
  { value: 'ELECTRICAL', label: 'Electrical Systems' },
  { value: 'MECHANICAL', label: 'Mechanical & Static/Rotary' },
  { value: 'INSTRUMENTATION', label: 'Instrumentation & Controls' },
  { value: 'HSE', label: 'Health, Safety & Environment (HSE)' },
  { value: 'OTHER', label: 'Other Engineering Discipline' },
];

const CANONICAL_FIELD_LABELS = {
  activity_code: { label: 'Activity Code / ID', required: true },
  activity_name: { label: 'Activity Name / Description', required: true },
  planned_start: { label: 'Planned Start Date', required: true },
  planned_finish: { label: 'Planned Finish Date', required: true },
  wbs_code: { label: 'WBS Code', required: false },
  wbs_name: { label: 'WBS Name', required: false },
  schedule_level: { label: 'Schedule Level (e.g. L5, L6)', required: false },
  discipline: { label: 'Discipline', required: false },
  planned_duration: { label: 'Planned Duration', required: false },
  predecessors: { label: 'Predecessors', required: false },
};

const STATUS_OPTIONS = [
  { value: 'PLANNING', label: 'Planning & Setup' },
  { value: 'ACTIVE', label: 'Active Execution' },
  { value: 'ON_HOLD', label: 'On Hold' },
  { value: 'COMPLETED', label: 'Completed' },
];

export default function ProjectWorkspace() {
  const { projectId } = useParams();
  const { token, user } = useAuth();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState('dashboard');

  const [project, setProject] = useState(null);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Schedule status & data states
  const [scheduleStatus, setScheduleStatus] = useState(null);
  const [activities, setActivities] = useState([]);
  const [activitiesLoading, setActivitiesLoading] = useState(false);
  const [activitiesPage, setActivitiesPage] = useState(1);
  const [activitiesTotalPages, setActivitiesTotalPages] = useState(1);
  const [activitiesTotal, setActivitiesTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDiscipline, setSelectedDiscipline] = useState('ALL');
  const [selectedLevel, setSelectedLevel] = useState('ALL');
  const [selectedActivity, setSelectedActivity] = useState(null);

  // Helper to open Activity Detail drawer when clicking an item on Dashboard
  const handleSelectActivityById = async (actId) => {
    if (!actId) return;
    try {
      const res = await getActivity(token, projectId, actId);
      if (res.success && res.data) {
        setSelectedActivity(res.data);
      }
    } catch (err) {
      console.error('Failed to load activity detail:', err);
    }
  };

  // Edit Project Modal state
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editFormData, setEditFormData] = useState({
    name: '',
    description: '',
    location: '',
    planned_start_date: '',
    planned_end_date: '',
    status: 'PLANNING',
  });
  const [editError, setEditError] = useState('');
  const [isUpdating, setIsUpdating] = useState(false);

  // Assign Supervisor Modal state
  const [isAssignModalOpen, setIsAssignModalOpen] = useState(false);
  const [assignEmail, setAssignEmail] = useState('');
  const [assignDiscipline, setAssignDiscipline] = useState('CIVIL');
  const [assignError, setAssignError] = useState('');
  const [isAssigning, setIsAssigning] = useState(false);
  const [supervisorSuggestions, setSupervisorSuggestions] = useState([]);

  // Schedule Import Wizard Modal State
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [importStep, setImportStep] = useState(1); // 1: Select File, 2: Preview & Mapping, 3: Confirm
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [columnMapping, setColumnMapping] = useState({});
  const [isProcessingPreview, setIsProcessingPreview] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [importError, setImportError] = useState('');

  // Remove confirmation state
  const [memberToRemove, setMemberToRemove] = useState(null);
  const [isRemoving, setIsRemoving] = useState(false);
  const [actionSuccessMsg, setActionSuccessMsg] = useState('');

  // Execution & Progress Tracking states (Phase 5)
  const [executionSummary, setExecutionSummary] = useState(null);
  const [activityHistory, setActivityHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Progress Reporting Modal state
  const [isProgressModalOpen, setIsProgressModalOpen] = useState(false);
  const [progressTargetActivity, setProgressTargetActivity] = useState(null);
  const [progressUpdateType, setProgressUpdateType] = useState('PROGRESS');
  const [progressReportedDate, setProgressReportedDate] = useState(
    new Date().toISOString().split('T')[0]
  );
  const [progressPercentageVal, setProgressPercentageVal] = useState('');
  const [progressRemarks, setProgressRemarks] = useState('');
  const [progressError, setProgressError] = useState('');
  const [isSubmittingProgress, setIsSubmittingProgress] = useState(false);

  const isPlannerOwner = user?.role === 'PLANNER' && project?.is_owner;

  // Helper to derive available status actions based on state machine rules
  const getAvailableActions = useCallback((executionStatus, progressPercentage) => {
    const status = executionStatus || 'NOT_STARTED';
    const progress = progressPercentage || 0;

    switch (status) {
      case 'NOT_STARTED':
        return ['START'];

      case 'IN_PROGRESS': {
        const actions = [];
        if (progress < 99) {
          actions.push('PROGRESS');
        }
        actions.push('COMPLETE', 'ON_HOLD');
        return actions;
      }

      case 'ON_HOLD':
        return ['RESUME'];

      case 'COMPLETED':
      default:
        return []; // Completed activities are locked!
    }
  }, []);

  // Check if current user is authorized to report progress on a specific activity
  const canUserReportActivity = useCallback(
    (act) => {
      if (!act) return false;
      if (act.execution_status === 'COMPLETED') return false;

      const actions = getAvailableActions(act.execution_status, act.progress_percentage);
      if (actions.length === 0) return false;

      // Planners manage projects but do not report field progress updates
      if (user?.role === 'PLANNER') return false;

      if (user?.role === 'SUPERVISOR') {
        const userDisc = project?.assigned_discipline;
        return userDisc && act.discipline === userDisc && act.discipline !== 'UNASSIGNED';
      }
      return false;
    },
    [user?.role, project?.assigned_discipline, getAvailableActions]
  );

  // Fetch Core Project Data & Schedule Status & Execution Summary
  const fetchProjectData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [projRes, membersRes, schedRes, execSummaryRes] = await Promise.all([
        getProject(token, projectId),
        getProjectMembers(token, projectId),
        getScheduleStatus(token, projectId),
        getExecutionSummary(token, projectId),
      ]);

      if (projRes.success && projRes.data) {
        setProject(projRes.data);
        setEditFormData({
          name: projRes.data.name,
          description: projRes.data.description || '',
          location: projRes.data.location || '',
          planned_start_date: projRes.data.planned_start_date,
          planned_end_date: projRes.data.planned_end_date,
          status: projRes.data.status,
        });
      } else {
        setError(projRes.error || 'Unable to access project details.');
      }

      if (membersRes.success && membersRes.data) {
        setMembers(membersRes.data);
      }

      if (schedRes.success && schedRes.data) {
        setScheduleStatus(schedRes.data);
      }

      if (execSummaryRes.success && execSummaryRes.data) {
        setExecutionSummary(execSummaryRes.data);
      }
    } catch (err) {
      setError('A network error occurred while loading the project workspace.');
    } finally {
      setLoading(false);
    }
  }, [token, projectId]);

  // Fetch activity progress history when drawer opens
  useEffect(() => {
    if (selectedActivity && selectedActivity.id) {
      setHistoryLoading(true);
      getActivityProgressHistory(token, projectId, selectedActivity.id).then((res) => {
        if (res.success && res.data) {
          setActivityHistory(res.data);
        } else {
          setActivityHistory([]);
        }
        setHistoryLoading(false);
      });
    } else {
      setActivityHistory([]);
    }
  }, [token, projectId, selectedActivity]);

  // Helper to open Progress Reporting Modal
  const openProgressModal = (act, e) => {
    if (e) e.stopPropagation();
    if (!act || act.execution_status === 'COMPLETED') return;

    setProgressTargetActivity(act);
    setProgressError('');
    setProgressReportedDate(new Date().toISOString().split('T')[0]);
    setProgressRemarks('');

    const actions = getAvailableActions(act.execution_status, act.progress_percentage);
    const currentStatus = act.execution_status || 'NOT_STARTED';

    if (currentStatus === 'NOT_STARTED') {
      setProgressUpdateType('START');
      setProgressPercentageVal('');
    } else if (currentStatus === 'ON_HOLD') {
      setProgressUpdateType('RESUME');
      setProgressPercentageVal(act.progress_percentage || 0);
    } else if (currentStatus === 'IN_PROGRESS') {
      if (actions.includes('PROGRESS')) {
        setProgressUpdateType('PROGRESS');
        const nextPct = Math.min(99, Math.round((act.progress_percentage || 0) + 10));
        const minPct = (act.progress_percentage || 0) + 1;
        setProgressPercentageVal(nextPct >= minPct ? nextPct : minPct);
      } else {
        // If progress is 99%, intermediate PROGRESS is not available; default to COMPLETE
        setProgressUpdateType('COMPLETE');
        setProgressPercentageVal(100);
      }
    }

    setIsProgressModalOpen(true);
  };

  // Submit progress report / status transition
  const handleProgressSubmit = async (e) => {
    e.preventDefault();
    if (!progressTargetActivity || progressTargetActivity.execution_status === 'COMPLETED') return;
    setProgressError('');

    let pctVal = null;
    if (['PROGRESS', 'COMPLETE'].includes(progressUpdateType)) {
      pctVal = parseFloat(progressPercentageVal);
      if (isNaN(pctVal)) {
        setProgressError('Please enter a valid numeric progress percentage.');
        return;
      }
    }

    setIsSubmittingProgress(true);
    try {
      const res = await reportActivityProgress(token, projectId, progressTargetActivity.id, {
        updateType: progressUpdateType,
        reportedDate: progressReportedDate,
        progressPercentage: pctVal,
        remarks: progressRemarks,
      });

      if (res.success && res.data) {
        setIsProgressModalOpen(false);
        showTemporarySuccess(`Progress update (${progressUpdateType}) submitted successfully!`);
        
        // Refresh activity list & execution summary
        fetchActivitiesList();
        getExecutionSummary(token, projectId).then((sumRes) => {
          if (sumRes.success) setExecutionSummary(sumRes.data);
        });

        // If selected activity drawer is open, refresh detail & history
        if (selectedActivity && selectedActivity.id === progressTargetActivity.id) {
          getActivity(token, projectId, selectedActivity.id).then((actRes) => {
            if (actRes.success && actRes.data) setSelectedActivity(actRes.data);
          });
        }
      } else {
        setProgressError(res.error || 'Failed to submit progress update.');
      }
    } catch (err) {
      setProgressError('Network error while reporting progress.');
    } finally {
      setIsSubmittingProgress(false);
    }
  };

  // Fetch Activities for Schedule Table smoothly
  const fetchActivitiesList = useCallback(async () => {
    if (!scheduleStatus?.has_schedule) return;
    if (activities.length === 0) {
      setActivitiesLoading(true);
    }
    try {
      const res = await getActivities(token, projectId, {
        page: activitiesPage,
        pageSize: 50,
        search: searchQuery,
        discipline: selectedDiscipline,
        scheduleLevel: selectedLevel,
      });

      if (res.success && res.data) {
        setActivities(res.data.items);
        setActivitiesTotal(res.data.total);
        setActivitiesTotalPages(res.data.total_pages);
      }
    } catch (err) {
      console.error('Failed to load activities:', err);
    } finally {
      setActivitiesLoading(false);
    }
  }, [token, projectId, scheduleStatus?.has_schedule, activitiesPage, searchQuery, selectedDiscipline, selectedLevel, activities.length]);

  useEffect(() => {
    fetchProjectData();
  }, [fetchProjectData]);

  useEffect(() => {
    if (activeTab === 'schedule' && scheduleStatus?.has_schedule) {
      fetchActivitiesList();
    }
  }, [activeTab, fetchActivitiesList, scheduleStatus?.has_schedule]);

  // Load supervisor suggestions for quick assignment
  useEffect(() => {
    if (isPlannerOwner && isAssignModalOpen) {
      getSupervisors(token).then((res) => {
        if (res.success && res.data) {
          setSupervisorSuggestions(res.data);
        }
      });
    }
  }, [isPlannerOwner, isAssignModalOpen, token]);

  // Handle Edit Project Submit
  const handleEditSubmit = async (e) => {
    e.preventDefault();
    setEditError('');

    if (new Date(editFormData.planned_end_date) < new Date(editFormData.planned_start_date)) {
      setEditError('Planned End Date cannot be earlier than Planned Start Date.');
      return;
    }

    setIsUpdating(true);
    try {
      const result = await updateProject(token, projectId, editFormData);
      if (result.success && result.data) {
        setProject(result.data);
        setIsEditModalOpen(false);
        showTemporarySuccess('Project metadata updated successfully.');
      } else {
        setEditError(result.error || 'Failed to update project.');
      }
    } catch (err) {
      setEditError('Failed to communicate with update service.');
    } finally {
      setIsUpdating(false);
    }
  };

  // Handle Assign Supervisor Submit
  const handleAssignSubmit = async (e) => {
    e.preventDefault();
    setAssignError('');

    if (!assignEmail.trim()) {
      setAssignError('Please enter or select a supervisor email.');
      return;
    }

    setIsAssigning(true);
    try {
      const result = await addProjectMember(token, projectId, {
        email: assignEmail.trim(),
        discipline: assignDiscipline,
      });

      if (result.success && result.data) {
        setMembers((prev) => [...prev, result.data]);
        setAssignEmail('');
        setIsAssignModalOpen(false);
        showTemporarySuccess(`Supervisor assigned with ${result.data.discipline} discipline.`);
      } else {
        setAssignError(result.error || 'Failed to assign supervisor.');
      }
    } catch (err) {
      setAssignError('Failed to communicate with assignment service.');
    } finally {
      setIsAssigning(false);
    }
  };

  // Handle Remove Supervisor
  const handleConfirmRemove = async () => {
    if (!memberToRemove) return;
    setIsRemoving(true);
    try {
      const result = await removeProjectMember(token, projectId, memberToRemove.user_id);
      if (result.success) {
        setMembers((prev) => prev.filter((m) => m.user_id !== memberToRemove.user_id));
        setMemberToRemove(null);
        showTemporarySuccess('Supervisor successfully removed from project.');
      } else {
        alert(result.error || 'Failed to remove supervisor.');
      }
    } catch (err) {
      alert('An error occurred while removing the team member.');
    } finally {
      setIsRemoving(false);
    }
  };

  // Handle Schedule File Selection & Preview Step
  const handleFileSelect = async (file) => {
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['csv', 'xlsx'].includes(ext)) {
      setImportError(`Unsupported format .${ext}. Please select a .csv or .xlsx file.`);
      return;
    }

    setSelectedFile(file);
    setImportError('');
    setIsProcessingPreview(true);

    try {
      const res = await previewSchedule(token, projectId, file);
      if (res.success && res.data) {
        setPreviewData(res.data);
        setColumnMapping(res.data.detected_mapping || {});
        setImportStep(2);
      } else {
        setImportError(res.error || 'Failed to parse schedule file preview.');
      }
    } catch (err) {
      setImportError('Failed to connect to schedule preview service.');
    } finally {
      setIsProcessingPreview(false);
    }
  };

  // Handle Confirm Import
  const handleConfirmImport = async () => {
    if (!selectedFile || !columnMapping) return;

    // Validate required fields mapped
    for (const [key, meta] of Object.entries(CANONICAL_FIELD_LABELS)) {
      if (meta.required && !columnMapping[key]) {
        setImportError(`Required field '${meta.label}' is not mapped to a column.`);
        return;
      }
    }

    setIsImporting(true);
    setImportError('');

    try {
      const res = await importSchedule(token, projectId, selectedFile, columnMapping);
      if (res.success && res.data) {
        setIsImportModalOpen(false);
        showTemporarySuccess(`${res.data.activities_imported} baseline activities imported successfully!`);
        // Refresh project data & schedule status
        fetchProjectData();
        setActiveTab('schedule');
      } else {
        setImportError(res.error || 'Failed to import schedule.');
      }
    } catch (err) {
      setImportError('Failed to process schedule import.');
    } finally {
      setIsImporting(false);
    }
  };

  const showTemporarySuccess = (msg) => {
    setActionSuccessMsg(msg);
    setTimeout(() => {
      setActionSuccessMsg('');
    }, 4000);
  };

  const backLink = user?.role === 'PLANNER' ? '/planner' : '/supervisor';

  if (loading) {
    return (
      <div className="workspace-shell">
        <Navbar workspaceTitle="Project Workspace" />
        <main className="workspace-main">
          <div className="loading-card">
            <RefreshCw size={24} className="spin-icon" />
            <span>Loading Project Context &amp; Schedule...</span>
          </div>
        </main>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="workspace-shell">
        <Navbar workspaceTitle="Project Access Denied" />
        <main className="workspace-main">
          <div className="error-card">
            <AlertCircle size={32} className="error-icon" />
            <h2>Access Restricted / Project Not Found</h2>
            <p>{error || 'You do not have authorization to view this project.'}</p>
            <Link to={backLink} className="btn-primary" style={{ marginTop: '1rem' }}>
              Return to Workspace
            </Link>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="workspace-shell">
      <Navbar workspaceTitle={`Project: ${project.project_code}`} />

      <main className="workspace-main">
        {/* Navigation Breadcrumb */}
        <div className="page-header-row">
          <Link to={backLink} className="btn-back-link">
            <ArrowLeft size={16} />
            <span>Back to {user?.role === 'PLANNER' ? 'My Projects' : 'Assigned Projects'}</span>
          </Link>
        </div>

        {actionSuccessMsg && (
          <div className="auth-success-banner" role="status">
            <CheckCircle2 size={16} className="success-icon" />
            <span>{actionSuccessMsg}</span>
          </div>
        )}

        {/* Project Header Banner Card */}
        <section className="project-banner-card">
          <div className="project-banner-header">
            <div className="project-title-group">
              <div className="project-code-badge font-mono">
                <Tag size={14} />
                <span>{project.project_code}</span>
              </div>
              <h1 className="project-main-title">{project.name}</h1>
              {project.location && (
                <div className="project-location-strip">
                  <MapPin size={14} />
                  <span>{project.location}</span>
                </div>
              )}
            </div>

            <div className="project-banner-controls">
              <div className={`status-pill ${project.status.toLowerCase()}`}>
                <span className="status-dot-small"></span>
                <span>{project.status.replace('_', ' ')}</span>
              </div>

              {isPlannerOwner && (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setIsEditModalOpen(true)}
                >
                  <Edit3 size={15} />
                  <span>Edit Baseline Metadata</span>
                </button>
              )}
            </div>
          </div>

          {/* Context Strip (User Role & Discipline) */}
          <div className="project-user-context-strip">
            <div className="context-item">
              <span className="context-label">Your Role:</span>
              {user?.role === 'PLANNER' ? (
                <span className="context-badge planner-badge">
                  <Shield size={12} />
                  <span>Project Planner (Managing Owner)</span>
                </span>
              ) : (
                <span className="context-badge supervisor-badge">
                  <Briefcase size={12} />
                  <span>Supervisor • {project.assigned_discipline || 'Assigned'} Discipline</span>
                </span>
              )}
            </div>
            {project.creator_name && (
              <div className="context-item">
                <span className="context-label">Lead Planner:</span>
                <span className="context-value">{project.creator_name}</span>
              </div>
            )}
            {scheduleStatus?.has_schedule && (
              <div className="context-item">
                <span className="context-label">Baseline Schedule:</span>
                <span className="context-value font-mono">
                  {scheduleStatus.total_activities} Activities Loaded
                </span>
              </div>
            )}
          </div>
        </section>

        {/* Project Sub-navigation Tabs */}
        <nav className="workspace-nav-tabs">
          <button
            type="button"
            className={`tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            <Building2 size={15} />
            <span>Dashboard</span>
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'schedule' ? 'active' : ''}`}
            onClick={() => setActiveTab('schedule')}
          >
            <FileSpreadsheet size={15} />
            <span>Schedule Baseline</span>
            {scheduleStatus?.has_schedule && (
              <span className="tab-count-badge font-mono">
                {scheduleStatus.total_activities}
              </span>
            )}
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'ai' ? 'active' : ''}`}
            onClick={() => setActiveTab('ai')}
          >
            <Bot size={15} />
            <span>Project AI</span>
            <span className="tab-readonly-badge font-mono">
              READ-ONLY
            </span>
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'reports' ? 'active' : ''}`}
            onClick={() => setActiveTab('reports')}
          >
            <FileSpreadsheet size={15} />
            <span>Progress Reports</span>
          </button>
          {isPlannerOwner && (
            <button
              type="button"
              className={`tab-btn ${activeTab === 'review-center' ? 'active' : ''}`}
              onClick={() => setActiveTab('review-center')}
            >
              <ClipboardCheck size={15} />
              <span>Review Center</span>
            </button>
          )}
          {isPlannerOwner && (
            <button
              type="button"
              className={`tab-btn ${activeTab === 'schedule-sync' ? 'active' : ''}`}
              onClick={() => setActiveTab('schedule-sync')}
            >
              <RefreshCw size={15} />
              <span>Schedule Sync</span>
            </button>
          )}
          <button
            type="button"
            className={`tab-btn ${activeTab === 'analytics' ? 'active' : ''}`}
            onClick={() => setActiveTab('analytics')}
          >
            <TrendingUp size={15} />
            <span>Analytics</span>
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'memory' ? 'active' : ''}`}
            onClick={() => setActiveTab('memory')}
          >
            <History size={15} />
            <span>Project Memory</span>
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'team' ? 'active' : ''}`}
            onClick={() => setActiveTab('team')}
          >
            <Users size={15} />
            <span>Team</span>
            <span className="tab-count-badge font-mono">
              {members.length}
            </span>
          </button>
        </nav>

        {/* TAB 0: BATCH PROGRESS REPORT INGESTION (PHASE 9) */}
        {activeTab === 'reports' && (
          <ProgressReportsPage
            token={token}
            project={project}
            user={user}
            assignedDiscipline={project?.assigned_discipline}
          />
        )}

        {/* TAB: PLANNER REVIEW CENTER (PHASE 10) */}
        {activeTab === 'review-center' && isPlannerOwner && (
          <PlannerReviewCenterTab
            projectId={projectId}
            token={token}
            user={user}
          />
        )}

        {/* TAB: SCHEDULE SYNC & ACTUALS EXPORT BRIDGE (PHASE 11) */}
        {activeTab === 'schedule-sync' && isPlannerOwner && (
          <ScheduleSyncTab
            projectId={projectId}
            projectCode={project?.project_code}
            projectName={project?.name}
            token={token}
            user={user}
          />
        )}

        {/* TAB: PROJECT ANALYTICS & FORECASTING (PHASE 12) */}
        {activeTab === 'analytics' && (
          <AnalyticsTab
            projectId={projectId}
            token={token}
            user={user}
            project={project}
            isPlannerOwner={isPlannerOwner}
            assignedDiscipline={project?.assigned_discipline}
            onSelectActivity={(actId) => handleSelectActivityById(actId)}
          />
        )}

        {/* TAB: INSTITUTIONAL PROJECT MEMORY (PHASE 14) */}
        {activeTab === 'memory' && (
          <ProjectMemoryTab
            projectId={projectId}
            token={token}
            user={user}
            project={project}
            isPlannerOwner={isPlannerOwner}
            assignedDiscipline={project?.assigned_discipline}
          />
        )}

        {/* TAB 1: REAL PROJECT CONTROL DASHBOARD */}
        {activeTab === 'dashboard' && (
          <DashboardTab
            projectId={projectId}
            token={token}
            isPlannerOwner={isPlannerOwner}
            assignedDiscipline={project?.assigned_discipline}
            onSelectActivity={(actId) => handleSelectActivityById(actId)}
            onNavigateToSchedule={() => setActiveTab('schedule')}
          />
        )}

        {/* TAB 2: SCHEDULE */}
        {activeTab === 'schedule' && (
          <div className="schedule-tab-content" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {!scheduleStatus?.has_schedule ? (
              <section className="workspace-panel-card">
                <div className="empty-team-state" style={{ padding: '3.5rem 2rem' }}>
                  <FileSpreadsheet size={48} className="empty-icon" />
                  <h3 style={{ fontSize: '1.25rem', color: 'var(--color-primary)', marginTop: '0.5rem' }}>
                    {isPlannerOwner ? 'No Baseline Schedule Imported' : 'No Baseline Schedule Available Yet'}
                  </h3>
                  <p style={{ maxWidth: '480px', margin: '0.25rem 0 1rem', fontSize: '0.875rem', color: 'var(--color-text-secondary)' }}>
                    {isPlannerOwner
                      ? 'Import a structured L5/L6 project schedule exported from Primavera P6 or Microsoft Project (.csv or .xlsx) to establish the execution baseline.'
                      : 'The project planner has not yet uploaded the baseline schedule for this project. Please check back later.'}
                  </p>
                  {isPlannerOwner && (
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={() => {
                        setIsImportModalOpen(true);
                        setImportStep(1);
                        setSelectedFile(null);
                        setPreviewData(null);
                        setImportError('');
                      }}
                    >
                      <Upload size={16} />
                      <span>Import Baseline Schedule</span>
                    </button>
                  )}
                </div>
              </section>
            ) : (
              <>
                {/* Schedule Filters & Toolbar */}
                <div className="schedule-filter-bar">
                  <div className="search-input-group">
                    <Search size={15} className="input-icon" />
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Search Activity ID, Name, or WBS..."
                      value={searchQuery}
                      onChange={(e) => {
                        setSearchQuery(e.target.value);
                        setActivitiesPage(1);
                      }}
                    />
                  </div>

                  <div className="filter-selects-group">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <Filter size={14} style={{ color: 'var(--color-text-muted)' }} />
                      <select
                        className="filter-select"
                        value={selectedDiscipline}
                        onChange={(e) => {
                          setSelectedDiscipline(e.target.value);
                          setActivitiesPage(1);
                        }}
                      >
                        <option value="ALL">All Disciplines</option>
                        <option value="CIVIL">Civil</option>
                        <option value="PIPING">Piping</option>
                        <option value="ELECTRICAL">Electrical</option>
                        <option value="MECHANICAL">Mechanical</option>
                        <option value="INSTRUMENTATION">Instrumentation</option>
                        <option value="HSE">HSE</option>
                        <option value="OTHER">Other</option>
                        <option value="UNASSIGNED">Unassigned</option>
                      </select>
                    </div>

                    <select
                      className="filter-select"
                      value={selectedLevel}
                      onChange={(e) => {
                        setSelectedLevel(e.target.value);
                        setActivitiesPage(1);
                      }}
                    >
                      <option value="ALL">All Levels</option>
                      <option value="L5">L5 Activities</option>
                      <option value="L6">L6 Activities</option>
                    </select>
                  </div>
                </div>

                {/* Schedule Table */}
                <div className="schedule-table-wrapper">
                  {activitiesLoading ? (
                    <div className="loading-card" style={{ border: 'none' }}>
                      <RefreshCw size={20} className="spin-icon" />
                      <span>Loading activities...</span>
                    </div>
                  ) : activities.length === 0 ? (
                    <div className="empty-team-state">
                      <p>No activities match your current search/filter criteria.</p>
                    </div>
                  ) : (
                    <table className="schedule-table">
                      <thead>
                        <tr>
                          <th>Activity ID</th>
                          <th>Activity Name</th>
                          <th>Discipline</th>
                          <th>Planned Start</th>
                          <th>Planned Finish</th>
                          <th>Actual Start</th>
                          <th>Actual Finish</th>
                          <th>Progress %</th>
                          <th>Status</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {activities.map((act) => {
                          const canReport = canUserReportActivity(act);
                          const statusLower = (act.execution_status || 'NOT_STARTED').toLowerCase();
                          return (
                            <tr
                              key={act.id}
                              className="clickable-row"
                              onClick={() => setSelectedActivity(act)}
                            >
                              <td className="font-mono" style={{ fontWeight: '700', color: 'var(--color-primary)' }}>
                                {act.activity_code}
                              </td>
                              <td style={{ maxWidth: '200px', whiteSpace: 'normal' }}>
                                <div style={{ fontWeight: '600' }}>{act.activity_name}</div>
                                {act.wbs_code && (
                                  <span className="font-mono" style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>
                                    {act.wbs_code}
                                  </span>
                                )}
                              </td>
                              <td>
                                <span className="discipline-tag">{act.discipline}</span>
                              </td>
                              <td className="font-mono">{act.planned_start}</td>
                              <td className="font-mono">{act.planned_finish}</td>
                              <td className="font-mono">{act.actual_start || '-'}</td>
                              <td className="font-mono">{act.actual_finish || '-'}</td>
                              <td style={{ width: '120px' }}>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                                  <span className="font-mono" style={{ fontSize: '0.75rem', fontWeight: '600' }}>
                                    {act.progress_percentage || 0}%
                                  </span>
                                  <div className="progress-bar-container">
                                    <div
                                      className={`progress-bar-fill ${statusLower}`}
                                      style={{ width: `${act.progress_percentage || 0}%` }}
                                    />
                                  </div>
                                </div>
                              </td>
                              <td>
                                <span className={`execution-pill ${statusLower}`}>
                                  <span className="status-dot-small" />
                                  <span>{(act.execution_status || 'NOT_STARTED').replace('_', ' ')}</span>
                                </span>
                              </td>
                              <td onClick={(e) => e.stopPropagation()}>
                                {canReport ? (
                                  <button
                                    type="button"
                                    className="btn-primary btn-sm"
                                    style={{ fontSize: '0.725rem', padding: '0.25rem 0.55rem' }}
                                    onClick={(e) => openProgressModal(act, e)}
                                  >
                                    <Clock size={12} />
                                    <span>Report</span>
                                  </button>
                                ) : (
                                  <span style={{ fontSize: '0.725rem', color: 'var(--color-text-muted)' }}>Read Only</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}
                </div>

                {/* Pagination Controls */}
                <div className="pagination-bar">
                  <span>
                    Showing {activities.length} of {activitiesTotal} total activities
                  </span>
                  <div className="pagination-controls">
                    <button
                      type="button"
                      className="btn-secondary"
                      style={{ padding: '0.35rem 0.65rem' }}
                      disabled={activitiesPage <= 1}
                      onClick={() => setActivitiesPage((p) => Math.max(1, p - 1))}
                    >
                      <ChevronLeft size={14} />
                      <span>Prev</span>
                    </button>
                    <span className="font-mono" style={{ fontWeight: '600', padding: '0 0.5rem' }}>
                      Page {activitiesPage} of {activitiesTotalPages}
                    </span>
                    <button
                      type="button"
                      className="btn-secondary"
                      style={{ padding: '0.35rem 0.65rem' }}
                      disabled={activitiesPage >= activitiesTotalPages}
                      onClick={() => setActivitiesPage((p) => Math.min(activitiesTotalPages, p + 1))}
                    >
                      <span>Next</span>
                      <ChevronRight size={14} />
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* TAB 3: TEAM */}
        {activeTab === 'team' && (
          <section className="workspace-panel-card">
            <div className="panel-header">
              <div className="panel-header-title">
                <Users size={18} />
                <h3>Project Team &amp; Engineering Disciplines ({members.length})</h3>
              </div>
              {isPlannerOwner && (
                <button
                  type="button"
                  className="btn-primary btn-sm"
                  onClick={() => setIsAssignModalOpen(true)}
                >
                  <UserPlus size={14} />
                  <span>Assign Supervisor</span>
                </button>
              )}
            </div>

            {members.length === 0 ? (
              <div className="empty-team-state">
                <Users size={32} className="empty-icon" />
                <p>No supervisors assigned to this project yet.</p>
                {isPlannerOwner && (
                  <span className="empty-subtext">
                    Assign registered supervisors to delegate field execution reporting.
                  </span>
                )}
              </div>
            ) : (
              <div className="team-table-wrapper">
                <table className="team-table">
                  <thead>
                    <tr>
                      <th>Supervisor</th>
                      <th>Email</th>
                      <th>Discipline</th>
                      {isPlannerOwner && <th>Action</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((mem) => {
                      const isCurrentUser = mem.user_id === user?.id;
                      return (
                        <tr key={mem.id} className={isCurrentUser ? 'current-user-row' : ''}>
                          <td className="member-name-cell">
                            <strong>{mem.full_name}</strong>
                            {isCurrentUser && <span className="you-pill">You</span>}
                          </td>
                          <td className="member-email-cell font-mono">{mem.email}</td>
                          <td>
                            <span className="discipline-tag">{mem.discipline}</span>
                          </td>
                          {isPlannerOwner && (
                            <td>
                              <button
                                type="button"
                                className="btn-icon-danger"
                                title={`Remove ${mem.full_name}`}
                                onClick={() => setMemberToRemove(mem)}
                              >
                                <Trash2 size={14} />
                              </button>
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {/* TAB 4: PROJECT AI ASSISTANT (Phase 7) */}
        {activeTab === 'ai' && (
          <ProjectAITab
            token={token}
            project={project}
            user={user}
            assignedDiscipline={project?.assigned_discipline}
            onSelectActivityCode={async (actCode) => {
              try {
                const res = await getActivities(token, projectId, { search: actCode, pageSize: 1 });
                if (res.success && res.data && res.data.items && res.data.items.length > 0) {
                  const fullAct = await getActivity(token, projectId, res.data.items[0].id);
                  if (fullAct.success && fullAct.data) setSelectedActivity(fullAct.data);
                }
              } catch (e) {
                console.error('Failed to select activity by code', e);
              }
            }}
          />
        )}
      </main>

      {/* ====================================================================
          ACTIVITY DETAIL DRAWER
          ==================================================================== */}
      {selectedActivity && (() => {
        const canReport = canUserReportActivity(selectedActivity);
        const statusLower = (selectedActivity.execution_status || 'NOT_STARTED').toLowerCase();

        return (
          <div className="drawer-backdrop" onClick={() => setSelectedActivity(null)}>
            <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
              <div className="drawer-header">
                <div>
                  <span className="project-code-badge font-mono">{selectedActivity.activity_code}</span>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: '700', color: 'var(--color-primary)', marginTop: '0.25rem' }}>
                    {selectedActivity.activity_name}
                  </h3>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  {canReport && (
                    <button
                      type="button"
                      className="btn-primary btn-sm"
                      onClick={(e) => openProgressModal(selectedActivity, e)}
                    >
                      <Clock size={14} />
                      <span>Report Progress</span>
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn-icon-close"
                    onClick={() => setSelectedActivity(null)}
                  >
                    <X size={18} />
                  </button>
                </div>
              </div>

              <div className="drawer-body">
                {/* SECTION 1: ACTUAL EXECUTION STATUS */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', padding: '1rem', backgroundColor: '#F8FAFC', border: '1px solid var(--color-border)', borderRadius: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: '700', color: 'var(--color-primary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      Actual Field Execution
                    </span>
                    <span className={`execution-pill ${statusLower}`}>
                      <span className="status-dot-small" />
                      <span>{(selectedActivity.execution_status || 'NOT_STARTED').replace('_', ' ')}</span>
                    </span>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                      <span style={{ color: 'var(--color-text-secondary)' }}>Physical Progress:</span>
                      <span className="font-mono" style={{ fontWeight: '700', color: 'var(--color-primary)' }}>
                        {selectedActivity.progress_percentage || 0}%
                      </span>
                    </div>
                    <div className="progress-bar-container" style={{ height: '10px' }}>
                      <div
                        className={`progress-bar-fill ${statusLower}`}
                        style={{ width: `${selectedActivity.progress_percentage || 0}%` }}
                      />
                    </div>
                  </div>

                  <div className="overview-details-grid" style={{ marginTop: '0.25rem' }}>
                    <div className="detail-item">
                      <span className="detail-label">Actual Start</span>
                      <span className="detail-value font-mono">{selectedActivity.actual_start || 'Not Started'}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Actual Finish</span>
                      <span className="detail-value font-mono">{selectedActivity.actual_finish || 'In Progress'}</span>
                    </div>
                  </div>

                  {selectedActivity.execution_status === 'COMPLETED' && (
                    <div className="auth-success-banner" style={{ margin: '0.25rem 0 0', padding: '0.5rem 0.75rem', fontSize: '0.775rem' }}>
                      <CheckCircle size={15} />
                      <span>Activity Completed • Execution updates are locked after completion.</span>
                    </div>
                  )}

                  {user?.role === 'PLANNER' && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', display: 'flex', alignItems: 'center', gap: '0.35rem', fontStyle: 'italic', marginTop: '0.25rem' }}>
                      <Info size={13} style={{ color: 'var(--color-text-muted)' }} />
                      <span>Execution updates are reported by assigned field supervisors.</span>
                    </div>
                  )}

                  {user?.role === 'SUPERVISOR' && !canReport && selectedActivity.execution_status !== 'COMPLETED' && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', display: 'flex', alignItems: 'center', gap: '0.35rem', fontStyle: 'italic', marginTop: '0.25rem' }}>
                      <Info size={13} style={{ color: 'var(--color-text-muted)' }} />
                      <span>Read-only: Execution progress can only be updated by the assigned {selectedActivity.discipline || ''} supervisor.</span>
                    </div>
                  )}

                  {selectedActivity.last_updated_by_name && (
                    <div style={{ fontSize: '0.725rem', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <UserPlus size={12} />
                      <span>Last updated by {selectedActivity.last_updated_by_name} on {new Date(selectedActivity.last_updated_at).toLocaleDateString()}</span>
                    </div>
                  )}
                </div>

                {/* SECTION 2: BASELINE PLAN */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <h4 style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--color-primary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Baseline Schedule Target
                  </h4>
                  <div className="overview-details-grid">
                    <div className="detail-item">
                      <span className="detail-label">Discipline</span>
                      <span className="detail-value">
                        <span className="discipline-tag">{selectedActivity.discipline}</span>
                      </span>
                    </div>

                    <div className="detail-item">
                      <span className="detail-label">Schedule Level</span>
                      <span className="detail-value">
                        {selectedActivity.schedule_level ? (
                          <span className="level-badge">{selectedActivity.schedule_level}</span>
                        ) : (
                          'Unspecified'
                        )}
                      </span>
                    </div>

                    <div className="detail-item">
                      <span className="detail-label">Planned Start</span>
                      <span className="detail-value font-mono">{selectedActivity.planned_start}</span>
                    </div>

                    <div className="detail-item">
                      <span className="detail-label">Planned Finish</span>
                      <span className="detail-value font-mono">{selectedActivity.planned_finish}</span>
                    </div>

                    <div className="detail-item">
                      <span className="detail-label">Planned Duration</span>
                      <span className="detail-value font-mono">
                        {selectedActivity.planned_duration ? `${selectedActivity.planned_duration} days` : 'Not specified'}
                      </span>
                    </div>

                    <div className="detail-item">
                      <span className="detail-label">WBS Code</span>
                      <span className="detail-value font-mono">{selectedActivity.wbs_code || '-'}</span>
                    </div>
                  </div>

                  {selectedActivity.wbs_name && (
                    <div className="detail-item">
                      <span className="detail-label">WBS Name</span>
                      <span className="detail-value">{selectedActivity.wbs_name}</span>
                    </div>
                  )}

                  {selectedActivity.predecessors && (
                    <div className="scope-description-box">
                      <span className="scope-label">Predecessor Logic</span>
                      <span className="font-mono" style={{ fontSize: '0.85rem', color: 'var(--color-primary)' }}>
                        {selectedActivity.predecessors}
                      </span>
                    </div>
                  )}
                </div>

                {/* SECTION 3: PROGRESS AUDIT HISTORY */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '0.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <h4 style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--color-primary)', textTransform: 'uppercase', letterSpacing: '0.04em', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <History size={14} />
                      <span>Progress Audit History</span>
                    </h4>
                    <span className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                      {activityHistory.length} Updates
                    </span>
                  </div>

                  {historyLoading ? (
                    <div className="loading-card" style={{ padding: '1rem', border: 'none' }}>
                      <RefreshCw size={16} className="spin-icon" />
                      <span style={{ fontSize: '0.8rem' }}>Loading audit trail...</span>
                    </div>
                  ) : activityHistory.length === 0 ? (
                    <div className="empty-team-state" style={{ padding: '1rem' }}>
                      <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>No progress updates recorded yet.</p>
                    </div>
                  ) : (
                    <div className="timeline-container">
                      {activityHistory.map((up) => {
                        const typeLower = up.update_type.toLowerCase();
                        return (
                          <div key={up.id} className="timeline-item">
                            <div className={`timeline-badge ${typeLower}`} />
                            <div className="timeline-header">
                              <span className="timeline-title">
                                {up.update_type}
                                {up.progress_percentage !== null && ` (${up.progress_percentage}%)`}
                              </span>
                              <span className="timeline-date font-mono">{up.reported_date}</span>
                            </div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
                              Reported by {up.reported_by_name || `User #${up.reported_by_id}`} via {up.source_type}
                            </div>
                            {up.remarks && <p className="timeline-remarks">{up.remarks}</p>}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* ====================================================================
          MULTI-STEP SCHEDULE IMPORT MODAL (Planner only)
          ==================================================================== */}
      {isImportModalOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-dialog" style={{ maxWidth: importStep === 2 ? '780px' : '560px' }}>
            <div className="modal-header">
              <h2 className="modal-title">Import Project Baseline Schedule</h2>
              <button
                type="button"
                className="btn-icon-close"
                onClick={() => setIsImportModalOpen(false)}
              >
                <X size={18} />
              </button>
            </div>

            {/* Stepper Header */}
            <div className="wizard-stepper">
              <div className={`wizard-step ${importStep === 1 ? 'active' : importStep > 1 ? 'completed' : ''}`}>
                <span className="step-num">{importStep > 1 ? <Check size={14} /> : '1'}</span>
                <span>Select File</span>
              </div>
              <div className={`wizard-step ${importStep === 2 ? 'active' : importStep > 2 ? 'completed' : ''}`}>
                <span className="step-num">2</span>
                <span>Map Columns &amp; Validate</span>
              </div>
            </div>

            {importError && (
              <div className="auth-error-banner" role="alert" style={{ margin: '1rem 1.5rem 0' }}>
                <AlertCircle size={16} />
                <span>{importError}</span>
              </div>
            )}

            {/* STEP 1: SELECT FILE */}
            {importStep === 1 && (
              <div className="modal-body-pad">
                <label className="file-dropzone">
                  <Upload size={36} style={{ color: 'var(--color-primary)' }} />
                  <div>
                    <span style={{ fontWeight: '700', color: 'var(--color-primary)' }}>
                      Click to choose CSV or XLSX schedule export
                    </span>
                    <p style={{ fontSize: '0.775rem', color: 'var(--color-text-secondary)', marginTop: '0.25rem' }}>
                      Supports Primavera P6 and MS Project exported files (Max 10 MB, up to 10,000 activities)
                    </p>
                  </div>
                  <input
                    type="file"
                    accept=".csv,.xlsx"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        handleFileSelect(e.target.files[0]);
                      }
                    }}
                  />
                </label>

                {isProcessingPreview && (
                  <div className="loading-card" style={{ padding: '1.5rem' }}>
                    <RefreshCw size={20} className="spin-icon" />
                    <span>Parsing schedule columns and detecting header aliases...</span>
                  </div>
                )}
              </div>
            )}

            {/* STEP 2: MAPPING & PREVIEW */}
            {importStep === 2 && previewData && (() => {
              // Calculate active validation errors dynamically based on current columnMapping
              const activeErrors = (previewData.errors || []).filter((err) => {
                for (const [field, meta] of Object.entries(CANONICAL_FIELD_LABELS)) {
                  if (meta.required && columnMapping[field] && err.includes(`'${field}' is not mapped`)) {
                    return false; // Error resolved because field is now mapped
                  }
                }
                return true;
              });

              // Check if any required canonical field is currently unmapped
              const missingRequiredFields = Object.entries(CANONICAL_FIELD_LABELS)
                .filter(([field, meta]) => meta.required && !columnMapping[field])
                .map(([field, meta]) => meta.label);

              const hasUnmappedRequired = missingRequiredFields.length > 0;
              const isImportDisabled = isImporting || hasUnmappedRequired || activeErrors.length > 0;

              return (
                <>
                  <div className="modal-body-pad" style={{ gap: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span className="font-mono" style={{ fontSize: '0.85rem', fontWeight: '600' }}>
                        File: {previewData.filename} ({previewData.row_count} total rows)
                      </span>
                      <span className="discipline-tag">
                        {isImportDisabled
                          ? `${activeErrors.length + missingRequiredFields.length} Validation Issue(s)`
                          : 'Ready to Import'}
                      </span>
                    </div>

                    <div style={{ maxHeight: '300px', overflowY: 'auto', border: '1px solid var(--color-border)', borderRadius: '6px' }}>
                      <table className="mapping-table">
                        <thead>
                          <tr>
                            <th>Canonical Activity Field</th>
                            <th>Required?</th>
                            <th>File Column Heading</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(CANONICAL_FIELD_LABELS).map(([field, meta]) => (
                            <tr key={field}>
                              <td>
                                <strong>{meta.label}</strong>
                              </td>
                              <td>
                                {meta.required ? (
                                  <span style={{ color: 'var(--color-danger-text)', fontWeight: '700', fontSize: '0.75rem' }}>
                                    Required
                                  </span>
                                ) : (
                                  <span style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem' }}>Optional</span>
                                )}
                              </td>
                              <td>
                                <select
                                  className="form-input"
                                  style={{ padding: '0.35rem 0.5rem', fontSize: '0.8rem' }}
                                  value={columnMapping[field] || ''}
                                  onChange={(e) =>
                                    setColumnMapping({ ...columnMapping, [field]: e.target.value || null })
                                  }
                                >
                                  <option value="">-- Unmapped --</option>
                                  {previewData.headers.map((h) => (
                                    <option key={h} value={h}>
                                      {h}
                                    </option>
                                  ))}
                                </select>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {(activeErrors.length > 0 || hasUnmappedRequired) && (
                      <div className="auth-error-banner" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: '700' }}>
                          <AlertTriangle size={16} />
                          <span>The following validation issues must be resolved before import:</span>
                        </div>
                        <ul style={{ paddingLeft: '1.25rem', marginTop: '0.5rem', fontSize: '0.775rem' }}>
                          {missingRequiredFields.map((label, idx) => (
                            <li key={`unmapped-${idx}`}>Required canonical field '{label}' is not mapped to any column.</li>
                          ))}
                          {activeErrors.slice(0, 5).map((err, idx) => (
                            <li key={`err-${idx}`}>{err}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>

                  {/* Modal Footer Controls */}
                  <div className="modal-footer">
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => setImportStep(1)}
                    >
                      Back
                    </button>

                    <button
                      type="button"
                      className="btn-primary"
                      disabled={isImportDisabled}
                      onClick={handleConfirmImport}
                    >
                      {isImporting ? 'Importing Schedule...' : 'Confirm & Import Baseline Schedule'}
                    </button>
                  </div>
                </>
              );
            })()}
          </div>
        </div>
      )}

      {/* ====================================================================
          EDIT PROJECT MODAL (Planner only)
          ==================================================================== */}
      {isEditModalOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-dialog">
            <div className="modal-header">
              <h2 className="modal-title">Edit Project Baseline</h2>
              <button
                type="button"
                className="btn-icon-close"
                onClick={() => setIsEditModalOpen(false)}
              >
                <X size={18} />
              </button>
            </div>

            {editError && (
              <div className="auth-error-banner" role="alert" style={{ margin: '1rem 1.5rem 0' }}>
                <AlertCircle size={16} />
                <span>{editError}</span>
              </div>
            )}

            <form onSubmit={handleEditSubmit} className="modal-form">
              <div className="form-group">
                <label className="form-label">Project Title *</label>
                <input
                  type="text"
                  className="form-input"
                  value={editFormData.name}
                  onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })}
                  required
                />
              </div>

              <div className="form-row-2">
                <div className="form-group">
                  <label className="form-label">Location</label>
                  <input
                    type="text"
                    className="form-input"
                    value={editFormData.location}
                    onChange={(e) => setEditFormData({ ...editFormData, location: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Status</label>
                  <select
                    className="form-input"
                    value={editFormData.status}
                    onChange={(e) => setEditFormData({ ...editFormData, status: e.target.value })}
                  >
                    {STATUS_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-row-2">
                <div className="form-group">
                  <label className="form-label">Planned Start Date</label>
                  <input
                    type="date"
                    className="form-input font-mono"
                    value={editFormData.planned_start_date}
                    onChange={(e) =>
                      setEditFormData({ ...editFormData, planned_start_date: e.target.value })
                    }
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Planned Finish Date</label>
                  <input
                    type="date"
                    className="form-input font-mono"
                    value={editFormData.planned_end_date}
                    onChange={(e) =>
                      setEditFormData({ ...editFormData, planned_end_date: e.target.value })
                    }
                    required
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Description / Scope</label>
                <textarea
                  rows={3}
                  className="form-textarea"
                  value={editFormData.description}
                  onChange={(e) =>
                    setEditFormData({ ...editFormData, description: e.target.value })
                  }
                />
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setIsEditModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={isUpdating}>
                  {isUpdating ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ====================================================================
          ASSIGN SUPERVISOR MODAL (Planner only)
          ==================================================================== */}
      {isAssignModalOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-dialog">
            <div className="modal-header">
              <h2 className="modal-title">Assign Supervisor to Project</h2>
              <button
                type="button"
                className="btn-icon-close"
                onClick={() => setIsAssignModalOpen(false)}
              >
                <X size={18} />
              </button>
            </div>

            {assignError && (
              <div className="auth-error-banner" role="alert" style={{ margin: '1rem 1.5rem 0' }}>
                <AlertCircle size={16} />
                <span>{assignError}</span>
              </div>
            )}

            <form onSubmit={handleAssignSubmit} className="modal-form">
              <div className="form-group">
                <label className="form-label">Supervisor Corporate Email *</label>
                <input
                  type="email"
                  className="form-input font-mono"
                  placeholder="e.g. supervisor@company.com"
                  value={assignEmail}
                  onChange={(e) => setAssignEmail(e.target.value)}
                  list="supervisor-datalist"
                  required
                />
                <datalist id="supervisor-datalist">
                  {supervisorSuggestions.map((sup) => (
                    <option key={sup.id} value={sup.email}>
                      {sup.full_name} ({sup.email})
                    </option>
                  ))}
                </datalist>
                <span className="form-help-text">
                  Supervisor must have a registered KaryaSetu account with the SUPERVISOR role.
                </span>
              </div>

              <div className="form-group">
                <label className="form-label">Assigned Engineering Discipline *</label>
                <select
                  className="form-input"
                  value={assignDiscipline}
                  onChange={(e) => setAssignDiscipline(e.target.value)}
                >
                  {DISCIPLINES.map((d) => (
                    <option key={d.value} value={d.value}>
                      {d.label} ({d.value})
                    </option>
                  ))}
                </select>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setIsAssignModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={isAssigning}>
                  {isAssigning ? 'Assigning...' : 'Assign Supervisor'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ====================================================================
          CONFIRM REMOVE SUPERVISOR MODAL
          ==================================================================== */}
      {memberToRemove && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-dialog modal-dialog-sm">
            <div className="modal-header">
              <h2 className="modal-title">Remove Supervisor</h2>
              <button
                type="button"
                className="btn-icon-close"
                onClick={() => setMemberToRemove(null)}
              >
                <X size={18} />
              </button>
            </div>
            <div className="modal-body-pad">
              <p>
                Are you sure you want to remove <strong>{memberToRemove.full_name}</strong> (
                {memberToRemove.discipline}) from this project team?
              </p>
              <p className="remove-warning-text">
                They will immediately lose access to this project workspace and its baseline data.
              </p>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setMemberToRemove(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-danger"
                onClick={handleConfirmRemove}
                disabled={isRemoving}
              >
                {isRemoving ? 'Removing...' : 'Confirm Remove'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ====================================================================
          PROGRESS REPORTING MODAL (Phase 5)
          ==================================================================== */}
      {isProgressModalOpen && progressTargetActivity && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-dialog" style={{ maxWidth: '520px' }}>
            <div className="modal-header">
              <div>
                <span className="project-code-badge font-mono">{progressTargetActivity.activity_code}</span>
                <h2 className="modal-title" style={{ marginTop: '0.2rem', fontSize: '1.1rem' }}>
                  Report Activity Progress
                </h2>
              </div>
              <button
                type="button"
                className="btn-icon-close"
                onClick={() => setIsProgressModalOpen(false)}
              >
                <X size={18} />
              </button>
            </div>

            {progressError && (
              <div className="auth-error-banner" role="alert" style={{ margin: '1rem 1.5rem 0' }}>
                <AlertCircle size={16} />
                <span>{progressError}</span>
              </div>
            )}

            <form onSubmit={handleProgressSubmit} className="modal-form">
              <div style={{ backgroundColor: '#F8FAFC', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--color-border)', fontSize: '0.825rem' }}>
                <div style={{ fontWeight: '700', color: 'var(--color-primary)' }}>{progressTargetActivity.activity_name}</div>
                <div style={{ display: 'flex', gap: '1rem', marginTop: '0.25rem', color: 'var(--color-text-secondary)' }}>
                  <span>Discipline: <strong>{progressTargetActivity.discipline}</strong></span>
                  <span>Current: <strong>{progressTargetActivity.progress_percentage || 0}% ({(progressTargetActivity.execution_status || 'NOT_STARTED').replace('_', ' ')})</strong></span>
                </div>
              </div>

              {/* Action / Transition Type Selector */}
              {(() => {
                const availableActions = getAvailableActions(progressTargetActivity.execution_status, progressTargetActivity.progress_percentage);
                return (
                  <div className="form-group">
                    <label className="form-label">Action / Status Transition *</label>
                    <div className="action-type-grid">
                      <button
                        type="button"
                        className={`action-type-btn ${progressUpdateType === 'START' ? 'active' : ''}`}
                        disabled={!availableActions.includes('START')}
                        onClick={() => {
                          setProgressUpdateType('START');
                          setProgressPercentageVal('');
                        }}
                      >
                        <Play size={14} />
                        <span>START</span>
                      </button>

                      <button
                        type="button"
                        className={`action-type-btn ${progressUpdateType === 'PROGRESS' ? 'active' : ''}`}
                        disabled={!availableActions.includes('PROGRESS')}
                        onClick={() => {
                          setProgressUpdateType('PROGRESS');
                          const minPct = (progressTargetActivity.progress_percentage || 0) + 1;
                          const nextPct = Math.min(99, Math.round((progressTargetActivity.progress_percentage || 0) + 10));
                          setProgressPercentageVal(nextPct >= minPct ? nextPct : minPct);
                        }}
                      >
                        <TrendingUp size={14} />
                        <span>PROGRESS</span>
                      </button>

                      <button
                        type="button"
                        className={`action-type-btn ${progressUpdateType === 'COMPLETE' ? 'active' : ''}`}
                        disabled={!availableActions.includes('COMPLETE')}
                        onClick={() => {
                          setProgressUpdateType('COMPLETE');
                          setProgressPercentageVal(100);
                        }}
                      >
                        <CheckCircle size={14} />
                        <span>COMPLETE</span>
                      </button>

                      <button
                        type="button"
                        className={`action-type-btn ${progressUpdateType === 'ON_HOLD' ? 'active' : ''}`}
                        disabled={!availableActions.includes('ON_HOLD')}
                        onClick={() => {
                          setProgressUpdateType('ON_HOLD');
                          setProgressPercentageVal(progressTargetActivity.progress_percentage || 0);
                        }}
                      >
                        <Pause size={14} />
                        <span>ON HOLD</span>
                      </button>

                      <button
                        type="button"
                        className={`action-type-btn ${progressUpdateType === 'RESUME' ? 'active' : ''}`}
                        disabled={!availableActions.includes('RESUME')}
                        onClick={() => {
                          setProgressUpdateType('RESUME');
                          setProgressPercentageVal(progressTargetActivity.progress_percentage || 0);
                        }}
                      >
                        <RotateCcw size={14} />
                        <span>RESUME</span>
                      </button>
                    </div>
                  </div>
                );
              })()}

              {/* Reported Date */}
              <div className="form-group">
                <label className="form-label">Reported Execution Date *</label>
                <input
                  type="date"
                  className="form-input font-mono"
                  value={progressReportedDate}
                  onChange={(e) => setProgressReportedDate(e.target.value)}
                  required
                />
              </div>

              {/* Progress Percentage Input (For PROGRESS or COMPLETE) */}
              {['PROGRESS', 'COMPLETE'].includes(progressUpdateType) && (() => {
                if (progressUpdateType === 'COMPLETE') {
                  return (
                    <div className="form-group">
                      <label className="form-label">Physical Progress Percentage (%)</label>
                      <input
                        type="number"
                        className="form-input font-mono"
                        value="100"
                        disabled
                      />
                      <span className="form-help-text">Completion sets progress to 100% and records actual finish date.</span>
                    </div>
                  );
                }

                const curProg = progressTargetActivity.progress_percentage || 0;
                const minPct = Math.max(1, curProg + 1);
                const maxPct = 99;

                return (
                  <div className="form-group">
                    <label className="form-label">
                      New Physical Progress Percentage (%) *
                      <span style={{ fontWeight: '400', color: 'var(--color-text-muted)', marginLeft: '0.35rem' }}>
                        (Valid range: {minPct}% to {maxPct}%)
                      </span>
                    </label>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <input
                        type="number"
                        min={minPct}
                        max={maxPct}
                        step="1"
                        className="form-input font-mono"
                        value={progressPercentageVal}
                        onChange={(e) => setProgressPercentageVal(e.target.value)}
                        required
                      />
                      <input
                        type="range"
                        min={minPct}
                        max={maxPct}
                        value={progressPercentageVal || minPct}
                        onChange={(e) => setProgressPercentageVal(e.target.value)}
                        style={{ flex: 1 }}
                      />
                    </div>
                  </div>
                );
              })()}

              {/* Remarks */}
              <div className="form-group">
                <label className="form-label">Field Remarks / Observations</label>
                <textarea
                  rows={3}
                  className="form-textarea"
                  placeholder="Optional site comments, equipment used, delay notes, etc."
                  value={progressRemarks}
                  onChange={(e) => setProgressRemarks(e.target.value)}
                />
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setIsProgressModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={isSubmittingProgress}>
                  {isSubmittingProgress ? 'Submitting...' : 'Submit Progress Update'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}


      <footer className="footer">
        <p>© 2026 KaryaSetu • Infrastructure Project Baseline &amp; Schedule Database</p>
      </footer>
    </div>
  );
}
