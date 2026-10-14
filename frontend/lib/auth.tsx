"use client";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from "react";
import { api, setCsrf } from "./api";
export type User = {
  id: string;
  name: string;
  email: string;
  role: "customer" | "analyst";
};
type Session = { user: User; csrf_token: string };
type AuthState = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (name: string, email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
};
const AuthContext = createContext<AuthState | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api<Session>("/auth/me")
      .then((session) => {
        setUser(session.user);
        setCsrf(session.csrf_token);
      })
      .catch(() => {
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);
  function accept(session: Session) {
    setUser(session.user);
    setCsrf(session.csrf_token);
    return session.user;
  }
  async function login(email: string, password: string) {
    return accept(
      await api<Session>("/auth/login", {
        method: "POST",
        body: { email, password },
      }),
    );
  }
  async function register(name: string, email: string, password: string) {
    return accept(
      await api<Session>("/auth/register", {
        method: "POST",
        body: { name, email, password },
      }),
    );
  }
  async function logout() {
    await api("/auth/logout", { method: "POST" });
    setUser(null);
    setCsrf("");
  }
  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("Auth context is missing");
  return context;
}
