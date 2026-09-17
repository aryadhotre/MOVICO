import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { AUTH_EXPIRED_EVENT, auth as authApi, getToken, setToken } from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState(null);
  // "loading" until the stored token has been verified, so guarded routes do not
  // bounce a signed-in user to /login on first paint.
  const [status, setStatus] = useState(() => (getToken() ? 'loading' : 'anonymous'));

  const signOut = useCallback(() => {
    setToken(null);
    setUser(null);
    setStatus('anonymous');
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    const controller = new AbortController();

    if (!getToken()) {
      setStatus('anonymous');
      return () => controller.abort();
    }

    authApi
      .me(controller.signal)
      .then((profile) => {
        setUser(profile);
        setStatus('authenticated');
      })
      .catch((error) => {
        if (error.name === 'AbortError') return;
        // A rejected token is simply an anonymous session.
        setToken(null);
        setUser(null);
        setStatus('anonymous');
      });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    const handler = () => signOut();
    window.addEventListener(AUTH_EXPIRED_EVENT, handler);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handler);
  }, [signOut]);

  const signIn = useCallback(
    async (username, password) => {
      const result = await authApi.login(username, password);
      setToken(result.access_token);
      setUser(result.user);
      setStatus('authenticated');
      queryClient.clear();
      return result.user;
    },
    [queryClient],
  );

  const register = useCallback(
    async (payload) => {
      const result = await authApi.register(payload);
      setToken(result.access_token);
      setUser(result.user);
      setStatus('authenticated');
      queryClient.clear();
      return result.user;
    },
    [queryClient],
  );

  const value = useMemo(
    () => ({
      user,
      status,
      isAuthenticated: status === 'authenticated',
      isLoading: status === 'loading',
      signIn,
      register,
      signOut,
    }),
    [user, status, signIn, register, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>');
  return context;
}
