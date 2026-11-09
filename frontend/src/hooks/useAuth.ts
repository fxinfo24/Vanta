// Real JWT auth hook.
// The backend now implements /api/auth/* (register/login/me/change-password)
// with a Bearer-token guard on every /api route. The token is kept in
// localStorage and attached by the api service interceptor.

import { useCallback, useEffect, useState } from 'react';
import { apiService } from '@/services/api';

const TOKEN_KEY = 'vanta_token';

export interface AuthUser {
  id: number;
  email: string;
  username?: string | null;
  first_name?: string | null;
  last_name?: string | null;
}

export const useAuth = () => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchMe = useCallback(async (): Promise<AuthUser | null> => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setUser(null);
      setLoading(false);
      return null;
    }
    const res = await apiService.me();
    if (res.success && res.data?.user) {
      setUser(res.data.user);
      setLoading(false);
      return res.data.user;
    }
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
    setLoading(false);
    return null;
  }, []);

  useEffect(() => {
    fetchMe();
  }, [fetchMe]);

  const login = useCallback(async (email: string, password: string): Promise<boolean> => {
    const res = await apiService.login(email, password);
    if (res.success && res.data?.token && res.data?.user) {
      localStorage.setItem(TOKEN_KEY, res.data.token);
      setUser(res.data.user);
      return true;
    }
    return false;
  }, []);

  const register = useCallback(
    async (email: string, password: string, username?: string): Promise<{ ok: boolean; error?: string }> => {
      const res = await apiService.register(email, password, username);
      if (res.success && res.data?.token && res.data?.user) {
        localStorage.setItem(TOKEN_KEY, res.data.token);
        setUser(res.data.user);
        return { ok: true };
      }
      return { ok: false, error: res.error || 'Registration failed' };
    },
    []
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
  }, []);

  return {
    user,
    isAuthenticated: !!user,
    loading,
    login,
    register,
    logout,
    refreshMe: fetchMe,
    token: () => localStorage.getItem(TOKEN_KEY),
  };
};
