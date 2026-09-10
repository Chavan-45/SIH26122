import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { HardHat, Lock, Mail, AlertCircle, ArrowRight, RefreshCw, Layers } from 'lucide-react';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!email || !password) {
      setError('Please provide both your email address and password.');
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await login(email, password);
      if (result.success && result.user) {
        // Redirect based on user role
        const targetRoute =
          location.state?.from?.pathname ||
          (result.user.role === 'PLANNER' ? '/planner' : '/supervisor');
        navigate(targetRoute, { replace: true });
      } else {
        setError(result.error || 'Authentication failed. Please verify your credentials.');
      }
    } catch (err) {
      setError('Unable to reach the authentication service. Please check backend status.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-page-shell">
      {/* Top Simple Header */}
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
        <div className="auth-card">
          <div className="auth-card-header">
            <div className="auth-icon-badge">
              <Lock size={20} />
            </div>
            <h1 className="auth-title">Sign In to Platform</h1>
            <p className="auth-subtitle">
              Enter your credentials to access your project management workspace.
            </p>
          </div>

          {error && (
            <div className="auth-error-banner" role="alert">
              <AlertCircle size={16} className="error-icon" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="auth-form">
            <div className="form-group">
              <label htmlFor="login-email" className="form-label">
                Email Address
              </label>
              <div className="input-wrapper">
                <Mail size={16} className="input-icon" />
                <input
                  id="login-email"
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

            <div className="form-group">
              <label htmlFor="login-password" className="form-label">
                Password
              </label>
              <div className="input-wrapper">
                <Lock size={16} className="input-icon" />
                <input
                  id="login-password"
                  type="password"
                  className="form-input"
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isSubmitting}
                  autoComplete="current-password"
                  required
                />
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
                  <span>Signing In...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>

          <div className="auth-card-footer">
            <p className="auth-switch-text">
              Don't have an account?{' '}
              <Link to="/register" className="auth-switch-link">
                Create Account
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
