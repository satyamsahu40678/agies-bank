"use client";

import { FormEvent, useMemo, useState } from "react";
import { api, useResource, money } from "@/lib/api";
import {
  PageHeader,
  Card,
  StatusBadge,
  EmptyState,
  LoadingState,
  ErrorState,
  Button,
  Field,
  Modal,
  Notice,
} from "@/components/ui";

type Customer = {
  id: string;
  name: string;
  email: string;
  account_id: string;
  account_status: string;
  balance: string;
  kyc_status: string;
};

export default function CustomerAccounts() {
  const { data, loading, error, refresh } =
    useResource<Customer[]>("/analyst/customers");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [selected, setSelected] = useState<Customer | null>(null);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [success, setSuccess] = useState("");
  const customers = useMemo(
    () =>
      (data || []).filter(
        (customer) =>
          (status === "all" || customer.account_status === status) &&
          `${customer.name} ${customer.email} ${customer.id}`
            .toLowerCase()
            .includes(search.toLowerCase()),
      ),
    [data, search, status],
  );

  function openStatus(customer: Customer) {
    setSelected(customer);
    setReason("");
    setSubmitError("");
  }
  async function updateStatus(event: FormEvent) {
    event.preventDefault();
    if (!selected || saving) return;
    if (reason.trim().length < 10) {
      setSubmitError(
        "Record at least 10 characters explaining the account status change.",
      );
      return;
    }
    const nextStatus =
      selected.account_status === "frozen" ? "active" : "frozen";
    setSaving(true);
    setSubmitError("");
    try {
      await api(
        `/analyst/accounts/${encodeURIComponent(selected.account_id)}/status`,
        { method: "POST", body: { status: nextStatus, reason: reason.trim() } },
      );
      setSuccess(
        `${selected.name}'s account is now ${nextStatus}. The change and your rationale have been audited.`,
      );
      setSelected(null);
      await refresh();
    } catch (err) {
      setSubmitError(
        err instanceof Error
          ? err.message
          : "The account could not be updated.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="stack">
      <PageHeader
        eyebrow="CUSTOMER PROTECTION"
        title="Know who you protect."
        description="Customer account health, identity status, and governed controls in one place."
        action={
          <Button variant="secondary" onClick={refresh}>
            Refresh accounts
          </Button>
        }
      />
      {success && <Notice tone="success">{success}</Notice>}
      <div className="grid three">
        <Card>
          <span className="stat-label">Customer accounts</span>
          <div className="metric-value">{data?.length || 0}</div>
          <p className="muted">Available customer records</p>
        </Card>
        <Card>
          <span className="stat-label">Active accounts</span>
          <div className="metric-value">
            {
              (data || []).filter(
                (customer) => customer.account_status === "active",
              ).length
            }
          </div>
          <p className="muted">Enabled for account activity</p>
        </Card>
        <Card>
          <span className="stat-label">Frozen accounts</span>
          <div className="metric-value">
            {
              (data || []).filter(
                (customer) => customer.account_status === "frozen",
              ).length
            }
          </div>
          <p className="muted">Outgoing transfers restricted</p>
        </Card>
      </div>
      <Card>
        <div className="analyst-toolbar">
          <div>
            <label htmlFor="customer-search">Find a customer</label>
            <input
              className="input"
              id="customer-search"
              placeholder="Search by name, email, or customer ID…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="customer-status">Account status</label>
            <select
              className="select"
              id="customer-status"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="all">All accounts</option>
              <option value="active">Active</option>
              <option value="frozen">Frozen</option>
            </select>
          </div>
        </div>
      </Card>
      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={refresh} />
      ) : (
        <Card>
          <div className="row-between">
            <h2 className="section-title">Customer directory</h2>
            <span className="muted">
              {customers.length}{" "}
              {customers.length === 1 ? "customer" : "customers"}
            </span>
          </div>
          {customers.length ? (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Customer</th>
                    <th scope="col">Account reference</th>
                    <th scope="col">Balance</th>
                    <th scope="col">Identity</th>
                    <th scope="col">Account status</th>
                    <th scope="col">Controls</th>
                  </tr>
                </thead>
                <tbody>
                  {customers.map((customer) => (
                    <tr key={customer.id}>
                      <td>
                        <span className="analyst-table-title">
                          {customer.name}
                        </span>
                        <span className="muted analyst-table-subtitle">
                          {customer.email}
                        </span>
                      </td>
                      <td>
                        <span className="analyst-mono muted">
                          {customer.account_id.slice(0, 12)}
                        </span>
                      </td>
                      <td>{money(customer.balance)}</td>
                      <td>
                        <StatusBadge status={customer.kyc_status} />
                      </td>
                      <td>
                        <StatusBadge status={customer.account_status} />
                      </td>
                      <td>
                        <Button
                          variant={
                            customer.account_status === "frozen"
                              ? "secondary"
                              : "danger"
                          }
                          onClick={() => openStatus(customer)}
                          aria-label={`${customer.account_status === "frozen" ? "Unfreeze" : "Freeze"} account for ${customer.name}`}
                        >
                          {customer.account_status === "frozen"
                            ? "Unfreeze account"
                            : "Freeze account"}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title={
                search || status !== "all"
                  ? "No matching customers"
                  : "No customer accounts yet"
              }
              description={
                search || status !== "all"
                  ? "Try another search or account status."
                  : "Customer registrations appear here when their account is created."
              }
            />
          )}
        </Card>
      )}
      <Notice tone="info">
        Freezing an account prevents outgoing transfers. Customer balances are
        preserved, and every status change requires a recorded reason.
      </Notice>

      {selected && (
        <Modal
          title={
            selected.account_status === "frozen"
              ? "Restore account access?"
              : "Freeze this account?"
          }
          onClose={() => {
            if (!saving) setSelected(null);
          }}
        >
          <form className="stack" onSubmit={updateStatus}>
            <p className="muted">
              {selected.account_status === "frozen"
                ? `Restore outgoing transfers for ${selected.name}. Confirm that the risk has been reviewed before removing the restriction.`
                : `Restrict outgoing transfers for ${selected.name}. The account balance of ${money(selected.balance)} will be preserved.`}
            </p>
            <Field
              label="Reason for account status change"
              hint="A clear rationale is required and will be recorded in the audit trail."
            >
              <textarea
                className="textarea"
                name="reason"
                placeholder="Describe the evidence and reason for this account action…"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                minLength={10}
                maxLength={500}
                rows={4}
                disabled={saving}
                required
              />
            </Field>
            {submitError && <Notice tone="danger">{submitError}</Notice>}
            <div className="analyst-decision-actions">
              <Button
                type="submit"
                variant={
                  selected.account_status === "frozen" ? "primary" : "danger"
                }
                disabled={saving || reason.trim().length < 10}
              >
                {saving
                  ? "Updating account…"
                  : selected.account_status === "frozen"
                    ? "Confirm unfreeze"
                    : "Confirm freeze"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setSelected(null)}
                disabled={saving}
              >
                Cancel
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
