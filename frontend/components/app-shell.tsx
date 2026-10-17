"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import {
  ArrowRightLeft,
  BadgeCheck,
  Bell,
  BookOpen,
  Bot,
  BriefcaseBusiness,
  ChevronDown,
  CircleHelp,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  Search,
  Shield,
  ShieldCheck,
  Sparkles,
  Users,
  X,
  Activity,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/api";
import { Modal } from "./ui";
const customerNav = [
  {
    href: "/automations",
    label: "Automations",
    icon: Bot,
    group: "AGENT WORKSPACE",
    description: "Scheduled reviews, security watch and savings coaching",
  },
  {
    href: "/dashboard",
    label: "Overview",
    icon: LayoutDashboard,
    group: "YOUR WORKSPACE",
    description: "Accounts, spending and recent activity",
  },
  {
    href: "/insights",
    label: "Financial health",
    icon: Sparkles,
    description: "Proactive insights, savings goals and agent runs",
  },
  {
    href: "/payments",
    label: "Payments",
    icon: ArrowRightLeft,
    description: "Transfer money and manage beneficiaries",
  },
  {
    href: "/assistant",
    label: "AI assistant",
    icon: Sparkles,
    group: "INTELLIGENCE",
    description: "Your personal banking copilot",
  },
  {
    href: "/recommendations",
    label: "Discover",
    icon: BriefcaseBusiness,
    description: "Loans, insurance and affordability",
  },
  {
    href: "/documents",
    label: "Documents",
    icon: FileText,
    description: "Upload and ask questions about documents",
  },
  {
    href: "/security",
    label: "Security center",
    icon: ShieldCheck,
    group: "TRUST & CONTROL",
    description: "Device events, fraud alerts and simulation",
  },
  {
    href: "/kyc",
    label: "Identity verification",
    icon: BadgeCheck,
    description: "Submit ID and selfie for review",
  },
  {
    href: "/activity",
    label: "Agent activity",
    icon: Activity,
    description: "Transparent decision and tool history",
  },
];
const analystNav = [
  {
    href: "/analyst/operations",
    label: "Operations",
    icon: Activity,
    description: "Ledger reconciliation and durable job health",
  },
  {
    href: "/analyst",
    label: "Overview",
    icon: LayoutDashboard,
    group: "RISK OPERATIONS",
    description: "Live case metrics and account holds",
  },
  {
    href: "/analyst/cases",
    label: "Review cases",
    icon: Shield,
    description: "Evaluate evidence and resolve risk cases",
  },
  {
    href: "/analyst/customers",
    label: "Customers",
    icon: Users,
    description: "Account status and freeze controls",
  },
  {
    href: "/analyst/integrations",
    label: "Integrations",
    icon: Bot,
    description: "AI providers, connection checks and shared policies",
  },
  {
    href: "/analyst/audit",
    label: "Audit trail",
    icon: BookOpen,
    group: "GOVERNANCE",
    description: "Global auditable decision timeline",
  },
];
export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <span className="brand">
      <span className="brand-icon">
        <Shield size={23} strokeWidth={1.9} />
        <span />
      </span>
      {!compact && (
        <span>
          Aegis<span className="brand-light">Bank</span>
          <i />
        </span>
      )}
    </span>
  );
}
export function AppShell({
  role,
  children,
}: {
  role: "customer" | "analyst";
  children: ReactNode;
}) {
  const { user, loading, logout } = useAuth();
  const health = useResource<{ ai_mode: string; demo_enabled: boolean }>(
    "/health",
  );
  const router = useRouter();
  const pathname = usePathname();
  const [mobile, setMobile] = useState(false);
  const [search, setSearch] = useState(false);
  const [query, setQuery] = useState("");
  const [logoutError, setLogoutError] = useState("");
  const nav = role === "customer" ? customerNav : analystNav;
  useEffect(() => {
    if (!loading && !user) router.replace("/login");
    else if (!loading && user && user.role !== role)
      router.replace(user.role === "analyst" ? "/analyst" : "/dashboard");
  }, [loading, user, role, router]);
  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "k") {
        event.preventDefault();
        setSearch((value) => !value);
      }
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);
  useEffect(() => setMobile(false), [pathname]);
  async function signOut() {
    try {
      await logout();
      router.push("/login");
    } catch (err) {
      setLogoutError(err instanceof Error ? err.message : "Sign out failed");
    }
  }
  if (loading || !user || user.role !== role)
    return (
      <div className="session-loading">
        <Brand />
        <div className="loading-dots">
          <i />
          <i />
          <i />
        </div>
        <p>Opening your secure workspace…</p>
      </div>
    );
  return (
    <div className="app-shell">
      {mobile && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <aside className={`sidebar ${mobile ? "is-open" : ""}`}>
        <Link
          href={role === "analyst" ? "/analyst" : "/dashboard"}
          className="brand-link"
          aria-label="AegisBank overview"
        >
          <Brand />
        </Link>
        <div className="workspace-switch">
          <span className="workspace-switch-icon">
            {role === "analyst" ? (
              <Shield size={16} />
            ) : (
              <BriefcaseBusiness size={16} />
            )}
          </span>
          <div>
            <strong>
              {role === "analyst" ? "Risk operations" : "Personal banking"}
            </strong>
            <small>
              {role === "analyst"
                ? "Analyst workspace"
                : "Your everyday, elevated"}
            </small>
          </div>
        </div>
        <nav aria-label="Main navigation">
          {nav.map((item) => (
            <div key={item.href}>
              {item.group && <p className="nav-group">{item.group}</p>}
              <Link
                href={item.href}
                className={`nav-link ${pathname === item.href || (item.href === "/analyst/cases" && pathname.startsWith("/analyst/cases/")) ? "active" : ""}`}
                aria-current={pathname === item.href ? "page" : undefined}
              >
                <item.icon size={19} />
                <span>{item.label}</span>
                {item.label === "AI assistant" && (
                  <span className="nav-new">AI</span>
                )}
              </Link>
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="agent-status">
            <span className="pulse-dot" />
            <div>
              <strong>Your guard is always on</strong>
              <span>
                Governed agents ·{" "}
                {health.data?.ai_mode === "claude"
                  ? "Claude mode"
                  : health.data?.ai_mode === "openai"
                    ? "OpenAI mode"
                    : health.data?.ai_mode === "gemini"
                      ? "Gemini mode"
                      : health.data?.ai_mode === "openrouter"
                        ? "OpenRouter mode"
                        : health.data
                          ? "Local mode"
                          : "Connecting"}
              </span>
            </div>
            <Shield size={17} />
          </div>
          <Link href="/" className="sidebar-about">
            <CircleHelp size={17} />
            About AegisBank
          </Link>
          <button className="sidebar-logout" onClick={signOut}>
            <LogOut size={17} />
            Sign out
          </button>
          {logoutError && (
            <p role="alert" className="sidebar-error">
              {logoutError}
            </p>
          )}
          <div className="sidebar-footnote">
            {health.data?.demo_enabled
              ? "Synthetic banking sandbox"
              : "Governed banking workspace"}
            <br />
            {health.data?.demo_enabled
              ? "No real money is moved."
              : "Authenticated session controls."}
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            onClick={() => setMobile(true)}
            aria-label="Open navigation"
          >
            <Menu size={22} />
          </button>
          <div className="topbar-breadcrumb">
            {role === "analyst" ? "Operations" : "Workspace"}
            <span>/</span>
            <strong>
              {nav.find((item) => item.href === pathname)?.label ||
                (pathname.startsWith("/analyst/cases/")
                  ? "Case detail"
                  : "Overview")}
            </strong>
          </div>
          <button className="workspace-search" onClick={() => setSearch(true)}>
            <Search size={16} />
            <span>Search workspace</span>
            <kbd>⌘ K</kbd>
          </button>
          <div className="topbar-right">
            <Link
              href={role === "customer" ? "/security" : "/analyst/cases"}
              className="secure-label"
            >
              <span className="pulse-dot" />
              Secure session
            </Link>
            <Link
              href={role === "customer" ? "/security" : "/analyst/cases"}
              className="icon-button notification-button"
              aria-label={
                role === "customer"
                  ? "View security alerts"
                  : "View review cases"
              }
            >
              <Bell size={19} />
              <i />
            </Link>
            <div className="topbar-divider" />
            <div className="profile-avatar">
              {user.name
                .split(" ")
                .map((word) => word[0])
                .slice(0, 2)
                .join("")}
            </div>
            <div className="profile-copy">
              <strong>{user.name}</strong>
              <span>
                {role === "analyst" ? "Risk analyst" : "Personal account"}
              </span>
            </div>
          </div>
        </header>
        <main id="main-content" className="page-content">
          {children}
        </main>
        <footer className="app-footer">
          <span>
            <ShieldCheck size={13} />
            Designed for confidence. Built with transparency.
          </span>
          <span>
            AegisBank {health.data?.demo_enabled ? "sandbox" : "workspace"} ·
            INR
          </span>
        </footer>
      </div>
      {search && (
        <Modal title="Find your workspace" onClose={() => setSearch(false)}>
          <FieldSearch query={query} setQuery={setQuery} />
          <div className="command-results">
            {nav
              .filter((item) =>
                `${item.label} ${item.description}`
                  .toLowerCase()
                  .includes(query.toLowerCase()),
              )
              .map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setSearch(false)}
                >
                  <item.icon size={20} />
                  <div>
                    <strong>{item.label}</strong>
                    <p>{item.description}</p>
                  </div>
                  <ArrowRightLeft size={16} />
                </Link>
              ))}
            {!nav.some((item) =>
              `${item.label} ${item.description}`
                .toLowerCase()
                .includes(query.toLowerCase()),
            ) && (
              <p className="muted">
                No matching pages. Try payments, security or documents.
              </p>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
function FieldSearch({
  query,
  setQuery,
}: {
  query: string;
  setQuery: (query: string) => void;
}) {
  return (
    <label className="search-field">
      <Search size={19} />
      <input
        autoFocus
        aria-label="Search pages"
        placeholder="What would you like to do?"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
    </label>
  );
}
