import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import PlannerWorkspace from './pages/PlannerWorkspace';
import CreateProjectPage from './pages/CreateProjectPage';
import SupervisorWorkspace from './pages/SupervisorWorkspace';
import ProjectWorkspace from './pages/ProjectWorkspace';
import { RefreshCw } from 'lucide-react';

function RootRedirect() {
  const { user, loading, isAuthenticated } = useAuth();

  if (loading) {
    return (
      <div className="auth-loading-screen">
        <div className="loading-box">
          <RefreshCw size={24} className="spin-icon" />
          <span>Verifying platform session...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return user?.role === 'PLANNER' ? (
    <Navigate to="/planner" replace />
  ) : (
    <Navigate to="/supervisor" replace />
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Root dynamic redirect */}
          <Route path="/" element={<RootRedirect />} />

          {/* Authentication routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Protected Planner Workspaces */}
          <Route
            path="/planner"
            element={
              <ProtectedRoute allowedRoles={['PLANNER']}>
                <PlannerWorkspace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/planner/projects/new"
            element={
              <ProtectedRoute allowedRoles={['PLANNER']}>
                <CreateProjectPage />
              </ProtectedRoute>
            }
          />

          {/* Protected Supervisor Workspaces */}
          <Route
            path="/supervisor"
            element={
              <ProtectedRoute allowedRoles={['SUPERVISOR']}>
                <SupervisorWorkspace />
              </ProtectedRoute>
            }
          />

          {/* Shared Dynamic Project Workspace Context */}
          <Route
            path="/projects/:projectId"
            element={
              <ProtectedRoute>
                <ProjectWorkspace />
              </ProtectedRoute>
            }
          />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
