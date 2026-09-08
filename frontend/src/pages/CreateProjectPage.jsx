import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { createProject } from '../services/api';
import Navbar from '../components/Navbar';
import { PlusCircle, Calendar, MapPin, Tag, FileText, ArrowLeft, RefreshCw, AlertCircle } from 'lucide-react';

export default function CreateProjectPage() {
  const { token } = useAuth();
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    name: '',
    project_code: '',
    location: '',
    planned_start_date: '',
    planned_end_date: '',
    description: '',
  });

  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: name === 'project_code' ? value.toUpperCase() : value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!formData.name.trim() || !formData.project_code.trim()) {
      setError('Project Name and Project Code are required.');
      return;
    }

    if (!formData.planned_start_date || !formData.planned_end_date) {
      setError('Planned Start Date and Planned End Date are required.');
      return;
    }

    if (new Date(formData.planned_end_date) < new Date(formData.planned_start_date)) {
      setError('Planned End Date cannot be earlier than Planned Start Date.');
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await createProject(token, {
        name: formData.name.trim(),
        project_code: formData.project_code.trim(),
        location: formData.location.trim() || null,
        planned_start_date: formData.planned_start_date,
        planned_end_date: formData.planned_end_date,
        description: formData.description.trim() || null,
      });

      if (result.success && result.data) {
        navigate(`/projects/${result.data.id}`);
      } else {
        setError(result.error || 'Failed to create project.');
      }
    } catch (err) {
      setError('An unexpected error occurred while communicating with the server.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="workspace-shell">
      <Navbar workspaceTitle="New Baseline Project" />

      <main className="workspace-main">
        {/* Navigation Breadcrumb */}
        <div className="page-header-row">
          <Link to="/planner" className="btn-back-link">
            <ArrowLeft size={16} />
            <span>Back to My Projects</span>
          </Link>
        </div>

        <div className="project-form-card">
          <div className="form-card-header">
            <div className="form-icon-box">
              <PlusCircle size={22} />
            </div>
            <div>
              <h1 className="form-card-title">Create Infrastructure Project</h1>
              <p className="form-card-subtitle">
                Establish a new project baseline and define schedule boundary parameters.
              </p>
            </div>
          </div>

          {error && (
            <div className="auth-error-banner" role="alert">
              <AlertCircle size={16} className="error-icon" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="project-form">
            <div className="form-row-2">
              <div className="form-group">
                <label htmlFor="proj-name" className="form-label">
                  Project Title *
                </label>
                <div className="input-wrapper">
                  <FileText size={16} className="input-icon" />
                  <input
                    id="proj-name"
                    name="name"
                    type="text"
                    className="form-input"
                    placeholder="e.g. Oil Processing Facility Expansion"
                    value={formData.name}
                    onChange={handleChange}
                    disabled={isSubmitting}
                    required
                  />
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="proj-code" className="form-label">
                  Project Code * (Unique Identifier)
                </label>
                <div className="input-wrapper">
                  <Tag size={16} className="input-icon" />
                  <input
                    id="proj-code"
                    name="project_code"
                    type="text"
                    className="form-input font-mono uppercase"
                    placeholder="e.g. OIL-FAC-001"
                    value={formData.project_code}
                    onChange={handleChange}
                    disabled={isSubmitting}
                    required
                  />
                </div>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="proj-location" className="form-label">
                Site / Geographic Location
              </label>
              <div className="input-wrapper">
                <MapPin size={16} className="input-icon" />
                <input
                  id="proj-location"
                  name="location"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Assam, Sector 4 Extraction Block"
                  value={formData.location}
                  onChange={handleChange}
                  disabled={isSubmitting}
                />
              </div>
            </div>

            <div className="form-row-2">
              <div className="form-group">
                <label htmlFor="proj-start-date" className="form-label">
                  Planned Baseline Start Date *
                </label>
                <div className="input-wrapper">
                  <Calendar size={16} className="input-icon" />
                  <input
                    id="proj-start-date"
                    name="planned_start_date"
                    type="date"
                    className="form-input font-mono"
                    value={formData.planned_start_date}
                    onChange={handleChange}
                    disabled={isSubmitting}
                    required
                  />
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="proj-end-date" className="form-label">
                  Planned Baseline Finish Date *
                </label>
                <div className="input-wrapper">
                  <Calendar size={16} className="input-icon" />
                  <input
                    id="proj-end-date"
                    name="planned_end_date"
                    type="date"
                    className="form-input font-mono"
                    value={formData.planned_end_date}
                    onChange={handleChange}
                    disabled={isSubmitting}
                    required
                  />
                </div>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="proj-description" className="form-label">
                Project Scope &amp; Engineering Overview
              </label>
              <textarea
                id="proj-description"
                name="description"
                rows={4}
                className="form-textarea"
                placeholder="Provide details regarding the scope, disciplines involved, baseline constraints, or project specifications..."
                value={formData.description}
                onChange={handleChange}
                disabled={isSubmitting}
              />
            </div>

            <div className="form-actions-row">
              <Link to="/planner" className="btn-secondary">
                Cancel
              </Link>
              <button
                type="submit"
                className="btn-primary"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <RefreshCw size={16} className="spin-icon" />
                    <span>Creating Project Baseline...</span>
                  </>
                ) : (
                  <>
                    <PlusCircle size={16} />
                    <span>Create Project</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </main>

      <footer className="footer">
        <p>© 2026 SIH26122 • Phase 3 Project Management &amp; Access Controls</p>
      </footer>
    </div>
  );
}
