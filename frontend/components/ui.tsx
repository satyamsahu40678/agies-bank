"use client";
import { ButtonHTMLAttributes, ReactNode, useEffect, useRef } from "react";
import {
  ArrowUpRight,
  CircleAlert,
  LoaderCircle,
  ShieldCheck,
  X,
} from "lucide-react";
export function Button({
  variant = "primary",
  className = "",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  return (
    <button {...props} className={`button button-${variant} ${className}`}>
      {children}
    </button>
  );
}
export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={`card ${className}`}>{children}</section>;
}
export function PageHeader({
  title,
  eyebrow,
  description,
  action,
}: {
  title: string;
  eyebrow?: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="page-description">{description}</p>}
      </div>
      {action && <div className="page-action">{action}</div>}
    </div>
  );
}
export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function StatusBadge({ status }: { status: string }) {
  const text = status.replaceAll("_", " ");
  const tone = [
    "active",
    "approved",
    "posted",
    "completed",
    "verified",
    "resolved",
    "allowed",
    "low",
    "eligible",
  ].includes(status)
    ? "success"
    : ["rejected", "frozen", "high", "blocked"].includes(status)
      ? "danger"
      : [
            "held",
            "pending",
            "review",
            "pending_step_up",
            "medium",
            "pending_review",
            "step_up_required",
          ].includes(status)
        ? "warning"
        : "neutral";
  return (
    <span className={`status status-${tone}`}>
      <i />
      {text}
    </span>
  );
}
export function Notice({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: "info" | "success" | "warning" | "danger";
}) {
  return (
    <div
      className={`notice notice-${tone}`}
      role={tone === "danger" ? "alert" : "status"}
    >
      {tone === "success" ? (
        <ShieldCheck size={17} />
      ) : (
        <CircleAlert size={17} />
      )}
      <div>{children}</div>
    </div>
  );
}
export function LoadingState() {
  return (
    <div className="loading-state" aria-label="Loading">
      <div className="skeleton-line" />
      <div className="grid three">
        {[1, 2, 3].map((key) => (
          <div className="skeleton-card" key={key} />
        ))}
      </div>
      <div className="skeleton-block" />
    </div>
  );
}
export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <Card>
      <div className="empty-state">
        <CircleAlert />
        <h3>Something needs attention</h3>
        <p>{message}</p>
        {onRetry && <Button onClick={onRetry}>Try again</Button>}
      </div>
    </Card>
  );
}
export function EmptyState({
  title = "Nothing here yet",
  description,
  children,
}: {
  title?: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <ArrowUpRight />
      </div>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {children}
    </div>
  );
}
export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    const first = ref.current?.querySelector<HTMLElement>(
      "button,input,select,textarea",
    );
    first?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeRef.current();
      if (event.key === "Tab") {
        const nodes = Array.from(
          ref.current?.querySelectorAll<HTMLElement>(
            "button:not([disabled]),input,select,textarea,a[href]",
          ) || [],
        );
        if (!nodes.length) return;
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", handler);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handler);
      document.body.style.overflow = overflow;
      before?.focus();
    };
  }, []);
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={ref}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="row-between">
          <h2>{title}</h2>
          <button
            className="icon-button"
            aria-label="Close dialog"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
export function Pending({ label = "Working…" }: { label?: string }) {
  return (
    <>
      <LoaderCircle size={16} className="spin" />
      {label}
    </>
  );
}
