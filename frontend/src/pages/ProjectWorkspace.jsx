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
  previewSchedule,
  importSchedule,
} from '../services/api';
import Navbar from '../components/Navbar';
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

  const [activeTab, setActiveTab] = useState('overview');

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

  const isPlannerOwner = user?.role === 'PLANNER' && project?.is_owner;

  // Fetch Core Project Data & Schedule Status
  const fetchProjectData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [projRes, membersRes, schedRes] = await Promise.all([
        getProject(token, projectId),
        getProjectMembers(token, projectId),
        getScheduleStatus(token, projectId),
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
    } catch (err) {
      setError('A network error occurred while loading the project workspace.');
    } finally {
      setLoading(false);
    }
  }, [token, projectId]);

  // Fetch Activities for Schedule Table
  const fetchActivitiesList = useCallback(async () => {
    if (!scheduleStatus?.has_schedule) return;
    setActivitiesLoading(true);
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
  }, [token, projectId, scheduleStatus?.has_schedule, activitiesPage, searchQuery, selectedDiscipline, selectedLevel]);

  useEffect(() => {
    fetchProjectData();
  }, [fetchProjectData]);

  useEffect(() => {
    if (activeTab === 'schedule' || scheduleStatus?.has_schedule) {
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
            className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            <Building2 size={16} />
            <span>Overview</span>
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'schedule' ? 'active' : ''}`}
            onClick={() => setActiveTab('schedule')}
          >
            <FileSpreadsheet size={16} />
            <span>Schedule Baseline</span>
            {scheduleStatus?.has_schedule && (
              <span className="level-badge font-mono" style={{ marginLeft: '0.25rem' }}>
                {scheduleStatus.total_activities}
              </span>
            )}
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'team' ? 'active' : ''}`}
            onClick={() => setActiveTab('team')}
          >
            <Users size={16} />
            <span>Team ({members.length})</span>
          </button>
        </nav>

        {/* TAB 1: OVERVIEW */}
        {activeTab === 'overview' && (
          <div className="overview-tab-content" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {/* Real Baseline KPI Cards if Schedule Exists */}
            {scheduleStatus?.has_schedule && (
              <section className="kpi-grid-4">
                <div className="kpi-card">
                  <span className="kpi-label">Total Scheduled Activities</span>
                  <span className="kpi-value font-mono">{scheduleStatus.total_activities}</span>
                </div>
                <div className="kpi-card">
                  <span className="kpi-label">Schedule Start</span>
                  <span className="kpi-value font-mono" style={{ fontSize: '1.1rem' }}>
                    {scheduleStatus.earliest_planned_start || project.planned_start_date}
                  </span>
                </div>
                <div className="kpi-card">
                  <span className="kpi-label">Schedule Finish</span>
                  <span className="kpi-value font-mono" style={{ fontSize: '1.1rem' }}>
                    {scheduleStatus.latest_planned_finish || project.planned_end_date}
                  </span>
                </div>
                <div className="kpi-card">
                  <span className="kpi-label">Disciplines Tracked</span>
                  <span className="kpi-value font-mono">
                    {Object.keys(scheduleStatus.discipline_counts || {}).length}
                  </span>
                </div>
              </section>
            )}

            <div className="project-grid-2">
              <section className="workspace-panel-card">
                <div className="panel-header">
                  <div className="panel-header-title">
                    <Building2 size={18} />
                    <h3>Project Metadata</h3>
                  </div>
                </div>

                <div className="overview-details-grid">
                  <div className="detail-item">
                    <span className="detail-label">Target Start Date</span>
                    <span className="detail-value font-mono">
                      <Calendar size={13} />
                      <span>{project.planned_start_date}</span>
                    </span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Target Finish Date</span>
                    <span className="detail-value font-mono">
                      <Calendar size={13} />
                      <span>{project.planned_end_date}</span>
                    </span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Status</span>
                    <span className="detail-value">{project.status.replace('_', ' ')}</span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Created At</span>
                    <span className="detail-value font-mono">
                      <Clock size={13} />
                      <span>{new Date(project.created_at).toLocaleDateString()}</span>
                    </span>
                  </div>
                </div>

                <div className="scope-description-box">
                  <span className="scope-label">Project Scope &amp; Description</span>
                  <p className="scope-text">
                    {project.description || 'No detailed description provided.'}
                  </p>
                </div>
              </section>

              {/* Schedule Summary on Overview tab */}
              <section className="workspace-panel-card">
                <div className="panel-header">
                  <div className="panel-header-title">
                    <FileSpreadsheet size={18} />
                    <h3>Schedule Baseline Summary</h3>
                  </div>
                  {isPlannerOwner && !scheduleStatus?.has_schedule && (
                    <button
                      type="button"
                      className="btn-primary btn-sm"
                      onClick={() => {
                        setIsImportModalOpen(true);
                        setImportStep(1);
                      }}
                    >
                      <Upload size={14} />
                      <span>Import Schedule</span>
                    </button>
                  )}
                </div>

                {scheduleStatus?.has_schedule ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                    <p style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
                      Baseline schedule imported from <strong>{scheduleStatus.latest_import?.original_filename}</strong> on{' '}
                      {new Date(scheduleStatus.latest_import?.imported_at).toLocaleDateString()}.
                    </p>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                      {Object.entries(scheduleStatus.discipline_counts || {}).map(([disc, count]) => (
                        <span key={disc} className="discipline-tag">
                          {disc}: {count}
                        </span>
                      ))}
                    </div>
                    <button
                      type="button"
                      className="btn-secondary"
                      style={{ alignSelf: 'flex-start', marginTop: '0.5rem' }}
                      onClick={() => setActiveTab('schedule')}
                    >
                      View Full Schedule Table →
                    </button>
                  </div>
                ) : (
                  <div className="empty-team-state">
                    <FileSpreadsheet size={32} className="empty-icon" />
                    <p>No baseline schedule imported yet.</p>
                    <span className="empty-subtext">
                      {isPlannerOwner
                        ? 'Upload Primavera P6 or MS Project CSV/XLSX export to establish L5/L6 activity baseline.'
                        : 'No baseline schedule is available yet for field tracking.'}
                    </span>
                    {isPlannerOwner && (
                      <button
                        type="button"
                        className="btn-primary btn-sm"
                        style={{ marginTop: '0.75rem' }}
                        onClick={() => {
                          setIsImportModalOpen(true);
                          setImportStep(1);
                        }}
                      >
                        <Upload size={14} />
                        <span>Import Schedule</span>
                      </button>
                    )}
                  </div>
                )}
              </section>
            </div>
          </div>
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
                          <th>WBS</th>
                          <th>Level</th>
                          <th>Discipline</th>
                          <th>Planned Start</th>
                          <th>Planned Finish</th>
                          <th>Duration</th>
                        </tr>
                      </thead>
                      <tbody>
                        {activities.map((act) => (
                          <tr
                            key={act.id}
                            className="clickable-row"
                            onClick={() => setSelectedActivity(act)}
                          >
                            <td className="font-mono" style={{ fontWeight: '700', color: 'var(--color-primary)' }}>
                              {act.activity_code}
                            </td>
                            <td>{act.activity_name}</td>
                            <td className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
                              {act.wbs_code ? `${act.wbs_code} ${act.wbs_name || ''}` : '-'}
                            </td>
                            <td>
                              {act.schedule_level ? (
                                <span className="level-badge">{act.schedule_level}</span>
                              ) : (
                                '-'
                              )}
                            </td>
                            <td>
                              <span className="discipline-tag">{act.discipline}</span>
                            </td>
                            <td className="font-mono">{act.planned_start}</td>
                            <td className="font-mono">{act.planned_finish}</td>
                            <td className="font-mono">
                              {act.planned_duration ? `${act.planned_duration}d` : '-'}
                            </td>
                          </tr>
                        ))}
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
      </main>

      {/* ====================================================================
          ACTIVITY DETAIL DRAWER
          ==================================================================== */}
      {selectedActivity && (
        <div className="drawer-backdrop" onClick={() => setSelectedActivity(null)}>
          <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <div>
                <span className="project-code-badge font-mono">{selectedActivity.activity_code}</span>
                <h3 style={{ fontSize: '1.15rem', fontWeight: '700', color: 'var(--color-primary)', marginTop: '0.25rem' }}>
                  {selectedActivity.activity_name}
                </h3>
              </div>
              <button
                type="button"
                className="btn-icon-close"
                onClick={() => setSelectedActivity(null)}
              >
                <X size={18} />
              </button>
            </div>

            <div className="drawer-body">
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
          </div>
        </div>
      )}

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
                  Supervisor must have a registered SIH26122 account with the SUPERVISOR role.
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

      <footer className="footer">
        <p>© 2026 SIH26122 • Infrastructure Project Baseline &amp; Schedule Database</p>
      </footer>
    </div>
  );
}
