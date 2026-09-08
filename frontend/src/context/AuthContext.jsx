import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { loginUser, registerUser, getMe } from '../services/api';

const AuthContext = createContext(null);

const TOKEN_KEY = 'sih26122_auth_token';

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Restore authenticated session on application mount
  const restoreSession = useCallback(async () => {
    const savedToken = localStorage.getItem(TOKEN_KEY);
    if (!savedToken) {
      setUser(null);
      setToken(null);
      setLoading(false);
      return;
    }

    try {
      const result = await getMe(savedToken);
      if (result.success && result.data) {
        setUser(result.data);
        setToken(savedToken);
      } else {
        // Token invalid or expired
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setUser(null);
      }
    } catch (err) {
      localStorage.removeItem(TOKEN_KEY);
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    restoreSession();
  }, [restoreSession]);

  const login = async (email, password) => {
    const result = await loginUser(email, password);
    if (result.success && result.data) {
      const { access_token, user: userData } = result.data;
      localStorage.setItem(TOKEN_KEY, access_token);
      setToken(access_token);
      setUser(userData);
      return { success: true, user: userData };
    }
    return { success: false, error: result.error };
  };

  const register = async (userData) => {
    const result = await registerUser(userData);
    if (result.success && result.data) {
      return { success: true, user: result.data };
    }
    return { success: false, error: result.error };
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        loading,
        login,
        register,
        logout,
        restoreSession,
        isAuthenticated: !!token && !!user,
        isPlanner: user?.role === 'PLANNER',
        isSupervisor: user?.role === 'SUPERVISOR',
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
