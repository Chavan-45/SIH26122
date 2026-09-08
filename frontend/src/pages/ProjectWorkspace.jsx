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

  const [project, setProject] = useState(null);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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

  // Remove confirmation state
  const [memberToRemove, setMemberToRemove] = useState(null);
  const [isRemoving, setIsRemoving] = useState(false);
  const [actionSuccessMsg, setActionSuccessMsg] = useState('');

  const isPlannerOwner = user?.role === 'PLANNER' && project?.is_owner;

  // Load project details and team members
  const fetchProjectData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [projRes, membersRes] = await Promise.all([
        getProject(token, projectId),
        getProjectMembers(token, projectId),
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
    } catch (err) {
      setError('A network error occurred while loading the project workspace.');
    } finally {
      setLoading(false);
    }
  }, [token, projectId]);

  useEffect(() => {
    fetchProjectData();
  }, [fetchProjectData]);

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
            <span>Loading Project Context &amp; Baselines...</span>
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
                  <span>Edit Project</span>
                </button>
              )}
            </div>
          </div>

          {/* Context Strip (User Role & Discipline) */}
          <div className="project-user-context-strip">
            <div className="context-item">
              <span className="context-label">Your Relationship:</span>
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
          </div>
        </section>

        {/* Project Details Grid */}
        <div className="project-grid-2">
          {/* Project Overview Card */}
          <section className="workspace-panel-card">
            <div className="panel-header">
              <div className="panel-header-title">
                <Building2 size={18} />
                <h3>Project Baseline Overview</h3>
              </div>
            </div>

            <div className="overview-details-grid">
              <div className="detail-item">
                <span className="detail-label">Planned Start Date</span>
                <span className="detail-value font-mono">
                  <Calendar size={13} />
                  <span>{project.planned_start_date}</span>
                </span>
              </div>

              <div className="detail-item">
                <span className="detail-label">Planned Finish Date</span>
                <span className="detail-value font-mono">
                  <Calendar size={13} />
                  <span>{project.planned_end_date}</span>
                </span>
              </div>

              <div className="detail-item">
                <span className="detail-label">Lifecycle Status</span>
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
                {project.description || 'No additional scope description specified for this baseline project.'}
              </p>
            </div>
          </section>

          {/* Project Team Section */}
          <section className="workspace-panel-card">
            <div className="panel-header">
              <div className="panel-header-title">
                <Users size={18} />
                <h3>Project Team &amp; Disciplines ({members.length})</h3>
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
        </div>
      </main>

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
        <p>© 2026 SIH26122 • Phase 3 Project Management &amp; Access Controls</p>
      </footer>
    </div>
  );
}
