import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, setAccessToken } from "./api";

export interface User {
  id: number;
  email: string;
  company_id: number;
  company_status: "ONBOARDING" | "LOCKED";
}

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState>(null!);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadMe() {
    const { data } = await api.get<User>("/auth/me");
    setUser(data);
  }

  async function startSession(path: string, email: string, password: string) {
    const { data } = await api.post<{ access_token: string }>(path, { email, password });
    setAccessToken(data.access_token);
    await loadMe();
  }

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.post<{ access_token: string }>("/auth/refresh");
        setAccessToken(data.access_token);
        await loadMe();
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const value: AuthState = {
    user,
    loading,
    login: (e, p) => startSession("/auth/login", e, p),
    register: (e, p) => startSession("/auth/register", e, p),
    logout: async () => {
      await api.post("/auth/logout");
      setAccessToken(null);
      setUser(null);
    },
    refreshUser: loadMe,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}