import React from 'react';
import { useAuth } from '../context/AuthContext';
import { HardHat, LogOut, User as UserIcon, Shield } from 'lucide-react';

export default function Navbar({ workspaceTitle }) {
  const { user, logout } = useAuth();

  return (
    <header className="header-bar">
      <div className="header-inner">
        <div className="logo-group">
          <div className="logo-icon-box">
            <HardHat size={22} className="logo-icon-svg" />
          </div>
          <div className="logo-text-block">
            <div className="logo-brand">SIH26122</div>
            <div className="logo-subtitle">Infrastructure Project Intelligence</div>
          </div>
        </div>

        <div className="nav-user-controls">
          {workspaceTitle && (
            <div className="workspace-pill font-mono">
              {workspaceTitle}
            </div>
          )}

          {user && (
            <div className="user-profile-badge">
              <div className="user-avatar-circle">
                <UserIcon size={14} />
              </div>
              <div className="user-details-text">
                <span className="user-name-text">{user.full_name}</span>
                <span className={`role-tag ${user.role.toLowerCase()}`}>
                  <Shield size={11} />
                  <span>{user.role}</span>
                </span>
              </div>
            </div>
          )}

          <button
            type="button"
            className="btn-logout"
            onClick={logout}
            title="Sign out of your session"
          >
            <LogOut size={15} />
            <span>Sign Out</span>
          </button>
        </div>
      </div>
    </header>
  );
}
