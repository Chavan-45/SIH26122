import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { HardHat, User, Mail, Lock, AlertCircle, CheckCircle2, ArrowRight, RefreshCw, Briefcase, Eye } from 'lucide-react';

export default function RegisterPage() {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [role, setRole] = useState('PLANNER'); // PLANNER or SUPERVISOR
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');

    // Frontend validation
    if (!fullName.trim() || !email.trim() || !password) {
      setError('All fields are required.');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Password confirmation does not match.');
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await register({
        fullName: fullName.trim(),
        email: email.trim(),
        password,
        role,
      });

      if (result.success) {
        setSuccessMsg('Account registered successfully! Redirecting to sign in...');
        setTimeout(() => {
          navigate('/login');
        }, 1500);
      } else {
        setError(result.error || 'Registration failed. Please check your details.');
      }
    } catch (err) {
      setError('Unable to connect to registration service. Please check backend status.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-page-shell">
      {/* Top Header */}
      <header className="auth-header">
        <div className="logo-group">
          <div className="logo-icon-box">
            <HardHat size={22} className="logo-icon-svg" />
          </div>
          <div className="logo-text-block">
            <div className="logo-brand">KaryaSetu</div>
            <div className="logo-subtitle">Infrastructure Project Intelligence</div>
          </div>
        </div>
      </header>

      {/* Center Auth Card */}
      <div className="auth-card-container">
        <div className="auth-card auth-card-register">
          <div className="auth-card-header">
            <div className="auth-icon-badge">
              <Briefcase size={20} />
            </div>
            <h1 className="auth-title">Create Platform Account</h1>
            <p className="auth-subtitle">
              Register your credentials and select your functional operational role.
            </p>
          </div>

          {error && (
            <div className="auth-error-banner" role="alert">
              <AlertCircle size={16} className="error-icon" />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="auth-success-banner" role="status">
              <CheckCircle2 size={16} className="success-icon" />
              <span>{successMsg}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="auth-form">
            <div className="form-group">
              <label htmlFor="reg-fullname" className="form-label">
                Full Name
              </label>
              <div className="input-wrapper">
                <User size={16} className="input-icon" />
                <input
                  id="reg-fullname"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Rajesh Kumar"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  disabled={isSubmitting}
                  required
                />
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="reg-email" className="form-label">
                Corporate / Project Email
              </label>
              <div className="input-wrapper">
                <Mail size={16} className="input-icon" />
                <input
                  id="reg-email"
                  type="email"
                  className="form-input"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={isSubmitting}
                  autoComplete="email"
                  required
                />
              </div>
            </div>

            <div className="form-row-2">
              <div className="form-group">
                <label htmlFor="reg-password" className="form-label">
                  Password
                </label>
                <div className="input-wrapper">
                  <Lock size={16} className="input-icon" />
                  <input
                    id="reg-password"
                    type="password"
                    className="form-input"
                    placeholder="Min. 6 chars"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={isSubmitting}
                    autoComplete="new-password"
                    required
                  />
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="reg-confirm-password" className="form-label">
                  Confirm Password
                </label>
                <div className="input-wrapper">
                  <Lock size={16} className="input-icon" />
                  <input
                    id="reg-confirm-password"
                    type="password"
                    className="form-input"
                    placeholder="Re-enter password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    disabled={isSubmitting}
                    autoComplete="new-password"
                    required
                  />
                </div>
              </div>
            </div>

            {/* Operational Role Selection */}
            <div className="form-group">
              <label className="form-label">Select Operational Role</label>
              <div className="role-selector-grid">
                <label
                  className={`role-option-card ${role === 'PLANNER' ? 'selected' : ''}`}
                >
                  <input
                    type="radio"
                    name="operational-role"
                    value="PLANNER"
                    checked={role === 'PLANNER'}
                    onChange={() => setRole('PLANNER')}
                    className="sr-only"
                    disabled={isSubmitting}
                  />
                  <div className="role-option-header">
                    <span className="role-radio-circle"></span>
                    <span className="role-option-title">Planner</span>
                  </div>
                  <p className="role-option-desc">
                    Schedule controls, L5/L6 project mapping, and master baseline management.
                  </p>
                </label>

                <label
                  className={`role-option-card ${role === 'SUPERVISOR' ? 'selected' : ''}`}
                >
                  <input
                    type="radio"
                    name="operational-role"
                    value="SUPERVISOR"
                    checked={role === 'SUPERVISOR'}
                    onChange={() => setRole('SUPERVISOR')}
                    className="sr-only"
                    disabled={isSubmitting}
                  />
                  <div className="role-option-header">
                    <span className="role-radio-circle"></span>
                    <span className="role-option-title">Supervisor</span>
                  </div>
                  <p className="role-option-desc">
                    Field execution, site progress capture (Civil, Piping, Electrical, Mechanical).
                  </p>
                </label>
              </div>
            </div>

            <button
              type="submit"
              className="btn-primary auth-submit-btn"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <RefreshCw size={16} className="spin-icon" />
                  <span>Creating Account...</span>
                </>
              ) : (
                <>
                  <span>Create Account</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>

          <div className="auth-card-footer">
            <p className="auth-switch-text">
              Already have an account?{' '}
              <Link to="/login" className="auth-switch-link">
                Sign In
              </Link>
            </p>
          </div>
        </div>
      </div>

      <footer className="footer auth-page-footer">
        <p>© 2026 KaryaSetu • Infrastructure Project Intelligence</p>
      </footer>
    </div>
  );
}
