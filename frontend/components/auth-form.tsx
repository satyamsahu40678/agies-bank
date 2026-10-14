"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Eye,
  EyeOff,
  ShieldCheck,
  Sparkles,
  LockKeyhole,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/api";
import { Brand } from "./app-shell";
import { Button, Field, Notice, Pending } from "./ui";
export function AuthForm({ register = false }: { register?: boolean }) {
  const { login, register: signUp } = useAuth();
  const health = useResource<{ demo_enabled: boolean }>("/health");
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy("form");
    setError("");
    try {
      const user = register
        ? await signUp(name, email, password)
        : await login(email, password);
      router.push(user.role === "analyst" ? "/analyst" : "/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in.");
    } finally {
      setBusy("");
    }
  }
  async function demo(role: "customer" | "analyst") {
    setBusy(role);
    setError("");
    try {
      const user = await login(
        role === "customer" ? "customer@aegis.demo" : "analyst@aegis.demo",
        role === "customer" ? "AegisDemo!2026" : "AegisAnalyst!2026",
      );
      router.push(user.role === "analyst" ? "/analyst" : "/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to open the demo.");
    } finally {
      setBusy("");
    }
  }
  return (
    <div className="auth-page">
      <div className="auth-aside">
        <Link href="/" className="auth-brand">
          <Brand />
        </Link>
        <div className="auth-story">
          <div className="hero-tag">
            <span className="pulse-dot" />
            INTELLIGENCE. WITH ACCOUNTABILITY.
          </div>
          <h1>
            Good decisions
            <br />
            start with
            <br />
            <span>peace of mind.</span>
          </h1>
          <p>
            Your money deserves more than a dashboard.
            <br />
            It deserves a team that looks ahead.
          </p>
          <div className="auth-mini-card">
            <span className="ai-orb">
              <Sparkles size={24} />
            </span>
            <div>
              <strong>Your five-agent advantage</strong>
              <p>
                Smarter guidance. Governed action.
                <br />A human in control, always.
              </p>
            </div>
          </div>
          <div className="auth-proof">
            <ShieldCheck size={17} />
            Session protected · Decisions transparent
          </div>
        </div>
        <p className="auth-aside-footer">
          AegisBank · Banking, intelligently protected.
        </p>
      </div>
      <main className="auth-main">
        <Link href="/" className="auth-back">
          Back to AegisBank <ArrowUpRight size={14} />
        </Link>
        <div className="auth-form-panel">
          <div className="auth-form-mark">
            <LockKeyhole size={22} />
          </div>
          <p className="eyebrow">YOUR SECURE WORKSPACE</p>
          <h2>
            {register ? "Make room for smarter banking." : "Welcome back."}
          </h2>
          <p className="auth-description">
            {register
              ? "Create your personal account and take the first step."
              : "A little clarity. A lot of confidence. Let’s get you in."}
          </p>
          {error && <Notice tone="danger">{error}</Notice>}
          <form onSubmit={submit} className="auth-form">
            {register && (
              <Field label="Full name">
                <input
                  name="name"
                  autoComplete="name"
                  required
                  maxLength={100}
                  placeholder="Your full name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </Field>
            )}
            <Field label="Email address">
              <input
                type="email"
                name="email"
                autoComplete="email"
                required
                placeholder="you@example.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </Field>
            <Field
              label="Password"
              hint={
                register
                  ? "Use at least 12 characters including upper and lowercase letters, a number, and a symbol."
                  : undefined
              }
            >
              <div className="password-field">
                <input
                  type={show ? "text" : "password"}
                  name="password"
                  autoComplete={register ? "new-password" : "current-password"}
                  required
                  minLength={register ? 12 : 1}
                  placeholder={
                    register ? "Create a strong password" : "Your password"
                  }
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
                <button
                  type="button"
                  onClick={() => setShow(!show)}
                  aria-label={show ? "Hide password" : "Show password"}
                >
                  {show ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
            </Field>
            <Button type="submit" disabled={!!busy}>
              {busy === "form" ? (
                <Pending
                  label={register ? "Creating account…" : "Signing in…"}
                />
              ) : (
                <>
                  {register ? "Create account" : "Sign in"}
                  <ArrowRight size={16} />
                </>
              )}
            </Button>
          </form>
          <p className="auth-switch">
            {register ? "Already have an account?" : "New to AegisBank?"}{" "}
            <Link href={register ? "/login" : "/register"}>
              {register ? "Sign in" : "Create an account"}
            </Link>
          </p>
          {health.data?.demo_enabled && (
            <div className="auth-demo">
              <div className="auth-divider">
                <span />
                EXPLORE THE LIVE SANDBOX
                <span />
              </div>
              <div className="grid two">
                <Button
                  variant="secondary"
                  disabled={!!busy}
                  onClick={() => demo("customer")}
                >
                  {busy === "customer" ? (
                    <Pending label="Opening…" />
                  ) : (
                    <>
                      Customer demo
                      <ArrowUpRight size={14} />
                    </>
                  )}
                </Button>
                <Button
                  variant="secondary"
                  disabled={!!busy}
                  onClick={() => demo("analyst")}
                >
                  {busy === "analyst" ? (
                    <Pending label="Opening…" />
                  ) : (
                    <>
                      Analyst demo
                      <ArrowUpRight size={14} />
                    </>
                  )}
                </Button>
              </div>
              <p>
                Preloaded synthetic data. No real money is moved.
                <br />
                New accounts start with a zero balance.
              </p>
            </div>
          )}
        </div>
        <div className="auth-security-note">
          <ShieldCheck size={13} />
          Your session is protected with secure authentication.
        </div>
      </main>
    </div>
  );
}
