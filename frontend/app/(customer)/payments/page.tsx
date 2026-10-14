"use client";

import { FormEvent, useRef, useState } from "react";
import { api, useResource, money, dateTime } from "@/lib/api";
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

type Beneficiary = {
  id: string;
  name: string;
  bank: string;
  account_last4: string;
  is_new: boolean;
};
type Transfer = {
  id: string;
  status: string;
  risk_score?: number;
  signals: { name: string; score: number; detail: string }[];
  decision: string;
  case_id?: string;
  message: string;
  amount?: string;
  beneficiary_name?: string;
};
type Transaction = {
  id: string;
  transfer_id?: string;
  amount: string;
  direction: string;
  description: string;
  category: string;
  status: string;
  created_at: string;
  balance_after: string;
};
type Overview = {
  account: { balance: string; status: string; currency: string };
};
type PaymentDraft = {
  beneficiary_id: string;
  amount: string;
  description: string;
  idempotency_key: string;
};

function errorMessage(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
}

export default function PaymentsPage() {
  const beneficiaries = useResource<Beneficiary[]>("/beneficiaries");
  const transactions = useResource<Transaction[]>("/transactions");
  const overview = useResource<Overview>("/overview");
  const [recipient, setRecipient] = useState("");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [draft, setDraft] = useState<PaymentDraft | null>(null);
  const [result, setResult] = useState<Transfer | null>(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const statusPanel = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [successTone, setSuccessTone] = useState<
    "success" | "warning" | "danger"
  >("success");
  const [showBeneficiary, setShowBeneficiary] = useState(false);
  const [beneficiaryName, setBeneficiaryName] = useState("");
  const [bank, setBank] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [beneficiaryError, setBeneficiaryError] = useState("");
  const [savingBeneficiary, setSavingBeneficiary] = useState(false);
  const [password, setPassword] = useState("");
  const [stepUpError, setStepUpError] = useState("");
  const selected = beneficiaries.data?.find(
    (entry) => entry.id === (draft?.beneficiary_id ?? recipient),
  );
  const isFrozen = overview.data?.account.status === "frozen";
  const pendingStepUp = result?.status === "pending_step_up";
  const verificationRequired = transactions.data?.some(
    (transaction) => transaction.status === "pending_step_up",
  );

  function resumeVerification(transaction: Transaction) {
    setResult({
      id: transaction.transfer_id || transaction.id,
      status: transaction.status,
      signals: [],
      decision: "step_up_required",
      amount: transaction.amount,
      message: `Additional verification is required for ${transaction.description}.`,
    });
    setStepUpError("");
    setPassword("");
    setError("");
    setSuccess("");
    statusPanel.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function reviewPayment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSuccess("");
    if (pendingStepUp) {
      setError(
        "Complete the verification for your previous transfer before starting another payment.",
      );
      return;
    }
    if (!recipient || !Number.isFinite(Number(amount)) || Number(amount) <= 0) {
      setError("Choose a recipient and enter an amount greater than zero.");
      return;
    }
    if (isFrozen) {
      setError(
        "Your account is frozen. Contact the security team before making a payment.",
      );
      return;
    }
    if (
      overview.data &&
      Number(amount) > Number(overview.data.account.balance)
    ) {
      setError("This amount exceeds your available balance.");
      return;
    }
    setDraft({
      beneficiary_id: recipient,
      amount: Number(amount).toFixed(2),
      description: description.trim() || "Bank transfer",
      idempotency_key: crypto.randomUUID(),
    });
  }

  async function confirmPayment() {
    if (!draft || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError("");
    try {
      const transfer = await api<Transfer>("/transfers", {
        method: "POST",
        body: draft,
      });
      setResult(transfer);
      setDraft(null);
      setAmount("");
      setDescription("");
      setPassword("");
      setStepUpError("");
      setSuccess(transfer.message);
      setSuccessTone(
        transfer.status === "posted"
          ? "success"
          : transfer.status === "rejected"
            ? "danger"
            : "warning",
      );
      await Promise.all([
        transactions.refresh(),
        overview.refresh(),
        beneficiaries.refresh(),
      ]);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  async function addBeneficiary(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (savingBeneficiary) return;
    setSavingBeneficiary(true);
    setBeneficiaryError("");
    try {
      const added = await api<Beneficiary>("/beneficiaries", {
        method: "POST",
        body: {
          name: beneficiaryName.trim(),
          bank: bank.trim(),
          account_number: accountNumber.replace(/\s/g, ""),
        },
      });
      await beneficiaries.refresh();
      setRecipient(added.id);
      setBeneficiaryName("");
      setBank("");
      setAccountNumber("");
      setShowBeneficiary(false);
      setSuccess(`${added.name} was added to your saved recipients.`);
      setSuccessTone("success");
    } catch (failure) {
      setBeneficiaryError(errorMessage(failure));
    } finally {
      setSavingBeneficiary(false);
    }
  }

  async function verifyPayment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!result || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setStepUpError("");
    try {
      const verified = await api<Transfer>(`/transfers/${result.id}/step-up`, {
        method: "POST",
        body: { password },
      });
      setResult(verified);
      setPassword("");
      setSuccess(verified.message);
      setSuccessTone(
        verified.status === "posted"
          ? "success"
          : verified.status === "rejected"
            ? "danger"
            : "warning",
      );
      await Promise.all([transactions.refresh(), overview.refresh()]);
    } catch (failure) {
      setStepUpError(errorMessage(failure));
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <PageHeader
        eyebrow="MOVE MONEY WITH CONFIDENCE"
        title="Payments"
        description="Pay a saved recipient, review every detail, and follow your transfer from request to completion."
        action={
          <Button
            variant="secondary"
            onClick={() => {
              setBeneficiaryError("");
              setShowBeneficiary(true);
            }}
          >
            Add recipient
          </Button>
        }
      />
      <div className="grid three">
        <Card>
          <div className="stat-label">Available balance</div>
          <div className="metric-value">
            {overview.data ? money(overview.data.account.balance) : "—"}
          </div>
          <div className="muted">
            {overview.data?.account.currency ?? "INR"} ·{" "}
            {overview.data?.account.status === "frozen"
              ? "Account frozen"
              : "Your primary account"}
          </div>
        </Card>
        <Card>
          <div className="stat-label">Saved recipients</div>
          <div className="metric-value">
            {beneficiaries.data?.length ?? "—"}
          </div>
          <div className="muted">Account details are securely masked</div>
        </Card>
        <Card>
          <div className="stat-label">Protection on every payment</div>
          <div className="metric-value" style={{ fontSize: "1.65rem" }}>
            Always active
          </div>
          <div className="muted">
            Identity, behavior, and transaction checks
          </div>
        </Card>
      </div>
      {isFrozen && (
        <Notice tone="danger">
          Your account is frozen. Outgoing payments are unavailable until the
          security team restores access.
        </Notice>
      )}
      {overview.error && (
        <Notice tone="warning">
          Your balance is temporarily unavailable. The bank will verify funds
          before processing a transfer.
        </Notice>
      )}
      {verificationRequired && !pendingStepUp && (
        <Notice tone="warning">
          A transfer is waiting for additional verification. Choose “Verify
          payment” in your transaction history to continue.
        </Notice>
      )}
      {success && (
        <div role="status">
          <Notice tone={successTone}>{success}</Notice>
        </div>
      )}
      {error && !draft && (
        <div role="alert">
          <Notice tone="danger">{error}</Notice>
        </div>
      )}
      <div className="grid two" style={{ alignItems: "start" }}>
        <Card>
          <div className="row-between">
            <h2 className="section-title">Make a transfer</h2>
            <span className="chip">INR payments</span>
          </div>
          <p className="muted">
            You will review your payment before it is submitted.
          </p>
          {beneficiaries.loading ? (
            <LoadingState />
          ) : beneficiaries.error ? (
            <ErrorState
              message={beneficiaries.error}
              onRetry={beneficiaries.refresh}
            />
          ) : (
            <form
              onSubmit={reviewPayment}
              className="stack"
              aria-label="Transfer money"
            >
              <Field label="Recipient">
                <select
                  className="select"
                  value={recipient}
                  onChange={(event) => setRecipient(event.target.value)}
                  required
                  aria-label="Recipient"
                >
                  <option value="">Choose a saved recipient</option>
                  {beneficiaries.data?.map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {entry.name} · {entry.bank} · •••• {entry.account_last4}
                    </option>
                  ))}
                </select>
              </Field>
              {selected && (
                <div
                  className="row-between"
                  style={{
                    background: "#f3f6f5",
                    borderRadius: 12,
                    padding: "12px 14px",
                  }}
                >
                  <div>
                    <strong>{selected.name}</strong>
                    <div className="muted">
                      {selected.bank} · Account ending {selected.account_last4}
                    </div>
                  </div>
                  {selected.is_new && (
                    <span className="chip">New recipient</span>
                  )}
                </div>
              )}
              {beneficiaries.data?.length === 0 && (
                <Notice tone="info">
                  Add your first recipient to make a transfer.
                </Notice>
              )}
              <Field
                label="Amount (INR)"
                hint="Amounts are processed in rupees, to two decimal places."
              >
                <input
                  className="input"
                  aria-label="Amount (INR)"
                  inputMode="decimal"
                  type="number"
                  min="0.01"
                  max="100000000"
                  step="0.01"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                  placeholder="0.00"
                  required
                />
              </Field>
              <Field
                label="Payment description"
                hint="A note to help you recognize this payment."
              >
                <input
                  className="input"
                  aria-label="Payment description"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="For example, October rent"
                  maxLength={200}
                />
              </Field>
              <Button
                type="submit"
                disabled={
                  busy ||
                  isFrozen ||
                  pendingStepUp ||
                  !beneficiaries.data?.length
                }
              >
                Review transfer
              </Button>
            </form>
          )}
        </Card>
        <div
          className="stack"
          ref={statusPanel}
          style={{ scrollMarginTop: 24 }}
        >
          {result ? (
            <Card>
              <div className="row-between">
                <h2 className="section-title">Latest transfer</h2>
                <StatusBadge status={result.status} />
              </div>
              {result.amount && (
                <div className="metric-value" style={{ marginTop: 14 }}>
                  {money(result.amount)}
                </div>
              )}
              {result.beneficiary_name && (
                <p className="muted">To {result.beneficiary_name}</p>
              )}
              <p>{result.message}</p>
              {typeof result.risk_score === "number" && (
                <div className="row-between">
                  <span className="muted">Risk assessment</span>
                  <strong>{result.risk_score}/100</strong>
                </div>
              )}
              <div className="divider" />
              {result.signals?.length > 0 && (
                <div className="stack" style={{ gap: 12 }}>
                  {result.signals.map((signal, index) => (
                    <div key={`${signal.name}-${index}`}>
                      <strong style={{ textTransform: "capitalize" }}>
                        {signal.name.replace(/_/g, " ")}
                      </strong>
                      <p className="muted" style={{ margin: "4px 0 0" }}>
                        {signal.detail}
                      </p>
                    </div>
                  ))}
                </div>
              )}
              {result.case_id && (
                <p className="muted">
                  A security analyst will review this payment. Case reference:{" "}
                  {result.case_id}.
                </p>
              )}
              {pendingStepUp && (
                <form
                  onSubmit={verifyPayment}
                  className="stack"
                  style={{ marginTop: 20 }}
                >
                  <Notice tone="warning">
                    Additional verification is required. This demo uses your
                    account password as a stand-in for production multi-factor
                    authentication.
                  </Notice>
                  <Field label="Account password (demo verification)">
                    <input
                      className="input"
                      aria-label="Account password (demo verification)"
                      type="password"
                      autoComplete="current-password"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      required
                    />
                  </Field>
                  {stepUpError && (
                    <div role="alert">
                      <Notice tone="danger">{stepUpError}</Notice>
                    </div>
                  )}
                  <Button type="submit" disabled={busy}>
                    {busy ? "Verifying…" : "Verify transfer"}
                  </Button>
                </form>
              )}
              <p
                className="muted"
                style={{
                  fontSize: 12,
                  overflowWrap: "anywhere",
                  marginBottom: 0,
                }}
              >
                Transfer reference: {result.id}
              </p>
            </Card>
          ) : (
            <Card>
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: 14,
                  background: "#e7f3ee",
                  display: "grid",
                  placeItems: "center",
                  color: "#147858",
                  fontSize: 25,
                  marginBottom: 20,
                }}
                aria-hidden="true"
              >
                ✓
              </div>
              <h2 className="section-title">
                A second look, before money moves
              </h2>
              <p className="muted">
                Aegis checks each transfer for unusual amounts, new recipients,
                and recent sign-in activity. Payments may require verification
                or analyst review.
              </p>
              <div className="divider" />
              <div className="stack" style={{ gap: 14 }}>
                <div>
                  <strong>01 · Choose your recipient</strong>
                  <p className="muted" style={{ margin: "4px 0 0" }}>
                    Confirm the bank and last four account digits.
                  </p>
                </div>
                <div>
                  <strong>02 · Review and confirm</strong>
                  <p className="muted" style={{ margin: "4px 0 0" }}>
                    You remain in control of every transfer.
                  </p>
                </div>
                <div>
                  <strong>03 · Track the outcome</strong>
                  <p className="muted" style={{ margin: "4px 0 0" }}>
                    See security decisions and payment status here.
                  </p>
                </div>
              </div>
            </Card>
          )}
          <Notice tone="info">
            This is a banking demonstration using synthetic funds. No real bank
            account is connected and no real money is moved.
          </Notice>
        </div>
      </div>
      <Card>
        <div className="row-between">
          <div>
            <h2 className="section-title">Recent transactions</h2>
            <p className="muted">
              Your latest account activity, including payments under review.
            </p>
          </div>
          <Button
            variant="ghost"
            onClick={() => transactions.refresh()}
            disabled={transactions.loading}
          >
            Refresh
          </Button>
        </div>
        {transactions.loading ? (
          <LoadingState />
        ) : transactions.error ? (
          <ErrorState
            message={transactions.error}
            onRetry={transactions.refresh}
          />
        ) : transactions.data?.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <caption className="sr-only">Recent account transactions</caption>
              <thead>
                <tr>
                  <th>Payment</th>
                  <th>Date</th>
                  <th>Status</th>
                  <th style={{ textAlign: "right" }}>Amount</th>
                  {verificationRequired && <th>Verification</th>}
                </tr>
              </thead>
              <tbody>
                {transactions.data.map((transaction) => (
                  <tr key={transaction.id}>
                    <td>
                      <strong>{transaction.description}</strong>
                      <div className="muted" style={{ fontSize: 12 }}>
                        {transaction.category}
                      </div>
                    </td>
                    <td>{dateTime(transaction.created_at)}</td>
                    <td>
                      <StatusBadge status={transaction.status} />
                    </td>
                    <td
                      style={{
                        textAlign: "right",
                        whiteSpace: "nowrap",
                        color:
                          transaction.direction === "credit"
                            ? "#147858"
                            : "inherit",
                      }}
                    >
                      {transaction.direction === "credit" ? "+" : "−"}
                      {money(transaction.amount)}
                    </td>
                    {verificationRequired && (
                      <td>
                        {transaction.status === "pending_step_up" ? (
                          <Button
                            variant="secondary"
                            aria-label={`Verify payment: ${transaction.description}`}
                            onClick={() => resumeVerification(transaction)}
                            disabled={busy}
                          >
                            Verify payment
                          </Button>
                        ) : (
                          "—"
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="No transactions yet"
            description="Your payment history will appear here after your first transfer."
          />
        )}
      </Card>
      {showBeneficiary && (
        <Modal
          title="Add a recipient"
          onClose={() => {
            if (!savingBeneficiary) setShowBeneficiary(false);
          }}
        >
          <p className="muted">
            Check the recipient’s account details carefully. Saved account
            numbers are masked after you add them.
          </p>
          <form
            onSubmit={addBeneficiary}
            className="stack"
            aria-label="Add a recipient"
          >
            <Field label="Recipient name">
              <input
                className="input"
                aria-label="Recipient name"
                value={beneficiaryName}
                onChange={(event) => setBeneficiaryName(event.target.value)}
                autoComplete="name"
                minLength={1}
                maxLength={100}
                required
              />
            </Field>
            <Field label="Bank name">
              <input
                className="input"
                aria-label="Bank name"
                value={bank}
                onChange={(event) => setBank(event.target.value)}
                minLength={1}
                maxLength={100}
                required
              />
            </Field>
            <Field label="Account number">
              <input
                className="input"
                aria-label="Account number"
                value={accountNumber}
                onChange={(event) => setAccountNumber(event.target.value)}
                inputMode="numeric"
                autoComplete="off"
                pattern="[0-9 ]{6,34}"
                minLength={6}
                maxLength={34}
                required
              />
            </Field>
            {beneficiaryError && (
              <div role="alert">
                <Notice tone="danger">{beneficiaryError}</Notice>
              </div>
            )}
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setShowBeneficiary(false)}
                disabled={savingBeneficiary}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={savingBeneficiary}>
                {savingBeneficiary ? "Saving…" : "Save recipient"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
      {draft && (
        <Modal
          title="Review your transfer"
          onClose={() => {
            if (!busy) {
              setDraft(null);
              setError("");
            }
          }}
        >
          <p className="muted">
            Confirm these details to submit your payment for security checks.
          </p>
          <div
            className="stack"
            style={{ borderRadius: 16, background: "#f3f6f5", padding: 20 }}
          >
            <div>
              <div className="stat-label">You are sending</div>
              <div className="metric-value">{money(draft.amount)}</div>
            </div>
            <div className="row-between">
              <span className="muted">To</span>
              <strong>{selected?.name}</strong>
            </div>
            <div className="row-between">
              <span className="muted">Bank</span>
              <span>{selected?.bank}</span>
            </div>
            <div className="row-between">
              <span className="muted">Account</span>
              <span>•••• {selected?.account_last4}</span>
            </div>
            <div>
              <div className="muted">Description</div>
              <strong style={{ overflowWrap: "anywhere" }}>
                {draft.description}
              </strong>
            </div>
          </div>
          <p className="muted">
            Your payment may be held for review or require additional
            verification. You will see the outcome immediately after submission.
          </p>
          {error && (
            <div role="alert">
              <Notice tone="danger">{error}</Notice>
            </div>
          )}
          <div
            className="row"
            style={{ justifyContent: "flex-end", marginTop: 20 }}
          >
            <Button
              variant="secondary"
              onClick={() => {
                setDraft(null);
                setError("");
              }}
              disabled={busy}
            >
              Back
            </Button>
            <Button onClick={confirmPayment} disabled={busy}>
              {busy ? "Processing…" : "Confirm transfer"}
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
