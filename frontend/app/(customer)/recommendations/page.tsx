"use client";

import { FormEvent, useRef, useState } from "react";
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
  Notice,
} from "@/components/ui";

type Loan = {
  id: string;
  name: string;
  rate: number;
  tenure_months: number;
  max_amount: string;
  eligible: boolean;
  reasons: string[];
  emi: string;
  illustrative_principal: string;
};
type Insurance = {
  id: string;
  name: string;
  monthly_premium: string;
  cover: string;
  eligible: boolean;
  reasons: string[];
};
type Recommendations = {
  profile: {
    monthly_income: string;
    monthly_expenses: string;
    credit_score: number;
    age: number;
  };
  loans: Loan[];
  insurance: Insurance[];
  disclaimer: string;
};
type Calculation = {
  emi: string;
  total_interest: string;
  total_payment: string;
  affordable: boolean;
};

export default function RecommendationsPage() {
  const recommendations = useResource<Recommendations>("/recommendations");
  const [principal, setPrincipal] = useState("300000");
  const [rate, setRate] = useState("10.5");
  const [tenure, setTenure] = useState("36");
  const [calculation, setCalculation] = useState<Calculation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [compared, setCompared] = useState<string[]>([]);
  const [selectedOffer, setSelectedOffer] = useState("");
  const calculator = useRef<HTMLElement>(null);
  const currentRequest = useRef(0);
  const profile = recommendations.data?.profile;
  const disposable = profile
    ? Number(profile.monthly_income) - Number(profile.monthly_expenses)
    : 0;
  const coverComparison =
    recommendations.data?.insurance.filter((item) =>
      compared.includes(item.id),
    ) ?? [];

  async function calculate(
    event?: FormEvent<HTMLFormElement>,
    chosen?: { principal: string; annual_rate: number; tenure_months: number },
  ) {
    event?.preventDefault();
    if (busy) return;
    const values = chosen ?? {
      principal,
      annual_rate: Number(rate),
      tenure_months: Number(tenure),
    };
    if (
      !Number.isFinite(Number(values.principal)) ||
      Number(values.principal) < 0.01 ||
      Number(values.principal) > 100000000 ||
      !Number.isFinite(values.annual_rate) ||
      values.annual_rate < 0 ||
      values.annual_rate > 50 ||
      !Number.isInteger(values.tenure_months) ||
      values.tenure_months < 1 ||
      values.tenure_months > 360
    ) {
      setError(
        "Enter a loan amount from ₹0.01 to ₹10 crore, a rate from 0–50%, and a term from 1–360 months.",
      );
      return;
    }
    const request = ++currentRequest.current;
    setBusy(true);
    setError("");
    try {
      const result = await api<Calculation>("/recommendations/calculate", {
        method: "POST",
        body: values,
      });
      if (request === currentRequest.current) setCalculation(result);
    } catch (failure) {
      if (request === currentRequest.current)
        setError(
          failure instanceof Error
            ? failure.message
            : "Unable to calculate repayments. Try again.",
        );
    } finally {
      if (request === currentRequest.current) setBusy(false);
    }
  }

  function previewLoan(loan: Loan) {
    const samplePrincipal = Number(loan.illustrative_principal);
    const availableAmount = Number(loan.max_amount);
    const offerPrincipal = String(
      samplePrincipal > 0
        ? samplePrincipal
        : availableAmount > 0
          ? Math.min(availableAmount, 300000)
          : 300000,
    );
    setPrincipal(offerPrincipal);
    setRate(String(loan.rate));
    setTenure(String(loan.tenure_months));
    setSelectedOffer(loan.name);
    calculator.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    void calculate(undefined, {
      principal: offerPrincipal,
      annual_rate: Number(loan.rate),
      tenure_months: loan.tenure_months,
    });
  }

  function editValue(setter: (value: string) => void, value: string) {
    setter(value);
    setCalculation(null);
    setSelectedOffer("");
  }
  function toggleComparison(id: string) {
    setCompared((selected) =>
      selected.includes(id)
        ? selected.filter((entry) => entry !== id)
        : [...selected, id],
    );
  }

  return (
    <div className="stack">
      <PageHeader
        eyebrow="PLAN YOUR NEXT CHAPTER"
        title="For your financial future"
        description="Understand your options with transparent eligibility checks, clear pricing, and repayment estimates built around your profile."
        action={
          <Button
            variant="secondary"
            onClick={() => recommendations.refresh()}
            disabled={recommendations.loading}
          >
            Refresh recommendations
          </Button>
        }
      />
      {recommendations.loading ? (
        <LoadingState />
      ) : recommendations.error ? (
        <ErrorState
          message={recommendations.error}
          onRetry={recommendations.refresh}
        />
      ) : recommendations.data ? (
        <>
          <div className="grid four">
            <Card>
              <div className="stat-label">Monthly income</div>
              <div className="metric-value">
                {money(profile!.monthly_income)}
              </div>
              <div className="muted">Estimated from account activity</div>
            </Card>
            <Card>
              <div className="stat-label">Monthly expenses</div>
              <div className="metric-value">
                {money(profile!.monthly_expenses)}
              </div>
              <div className="muted">Your current spending profile</div>
            </Card>
            <Card>
              <div className="stat-label">Room in your budget</div>
              <div
                className="metric-value"
                style={{ color: disposable >= 0 ? "#147858" : "#b42318" }}
              >
                {money(disposable)}
              </div>
              <div className="muted">Before new repayments</div>
            </Card>
            <Card>
              <div className="stat-label">Demo credit score</div>
              <div className="metric-value">
                {profile!.credit_score}
                <span style={{ fontSize: 16, color: "#76818d" }}> / 900</span>
              </div>
              <div className="muted">
                Synthetic profile · Age {profile!.age}
              </div>
            </Card>
          </div>
          <Notice tone="info">
            {recommendations.data.disclaimer ||
              "These are illustrative product recommendations based on synthetic data, not financial advice or a credit approval. No real loan or insurance application is submitted."}
          </Notice>
          <div className="row-between">
            <div>
              <h2 className="section-title" style={{ fontSize: 22 }}>
                Borrow with a clear view
              </h2>
              <p className="muted">
                Review the reasons behind each recommendation before exploring
                repayments.
              </p>
            </div>
            <span className="chip">Personalized loan options</span>
          </div>
          {recommendations.data.loans.length ? (
            <div className="grid three">
              {recommendations.data.loans.map((loan) => (
                <Card key={loan.id}>
                  <div className="row-between">
                    <span className="stat-label">Loan option</span>
                    <StatusBadge
                      status={loan.eligible ? "eligible" : "ineligible"}
                    />
                  </div>
                  <h3 style={{ fontSize: 20, margin: "16px 0" }}>
                    {loan.name}
                  </h3>
                  <div className="metric-value">
                    {loan.rate}%
                    <span
                      className="muted"
                      style={{ fontSize: 13, fontWeight: 400 }}
                    >
                      {" "}
                      p.a.
                    </span>
                  </div>
                  <div className="muted">Illustrative annual interest rate</div>
                  <div className="divider" />
                  <div className="stack" style={{ gap: 12 }}>
                    <div className="row-between">
                      <span className="muted">Up to</span>
                      <strong>{money(loan.max_amount)}</strong>
                    </div>
                    <div className="row-between">
                      <span className="muted">Typical term</span>
                      <strong>{loan.tenure_months} months</strong>
                    </div>
                    <div className="row-between">
                      <span className="muted">
                        {loan.illustrative_principal !== undefined
                          ? `EMI on ${money(loan.illustrative_principal)}`
                          : "Illustrative EMI"}
                      </span>
                      <strong>{money(loan.emi)} / mo</strong>
                    </div>
                  </div>
                  <div className="divider" />
                  <div className="stat-label">Why this fits your profile</div>
                  <ul
                    style={{ paddingLeft: 18, lineHeight: 1.65, fontSize: 14 }}
                  >
                    {loan.reasons.map((reason, index) => (
                      <li key={index}>{reason}</li>
                    ))}
                  </ul>
                  {!loan.eligible && (
                    <p className="muted" style={{ fontSize: 13 }}>
                      Your current profile does not meet this product’s demo
                      eligibility criteria. You can still explore repayment
                      costs.
                    </p>
                  )}
                  <Button
                    variant={loan.eligible ? "primary" : "secondary"}
                    onClick={() => previewLoan(loan)}
                    disabled={busy}
                    style={{ width: "100%" }}
                  >
                    Estimate repayments
                  </Button>
                </Card>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No loan recommendations available"
              description="Your profile does not have enough activity for a recommendation. You can still use the repayment calculator."
            />
          )}
          <section
            ref={calculator}
            style={{ scrollMarginTop: 24 }}
            aria-labelledby="calculator-title"
          >
            <Card>
              <div className="row-between">
                <div>
                  <h2 id="calculator-title" className="section-title">
                    Build a repayment plan
                  </h2>
                  <p className="muted">
                    Adjust the amount, interest rate, and term to estimate a
                    monthly payment.
                  </p>
                </div>
                <span className="chip">EMI calculator</span>
              </div>
              {selectedOffer && (
                <Notice tone="info">
                  Exploring {selectedOffer}. You can change any value below.
                </Notice>
              )}
              <div
                className="grid two"
                style={{ alignItems: "start", marginTop: 20 }}
              >
                <form
                  className="stack"
                  onSubmit={calculate}
                  aria-label="Loan repayment calculator"
                >
                  <Field label="Loan amount (INR)">
                    <input
                      className="input"
                      aria-label="Loan amount (INR)"
                      type="number"
                      inputMode="decimal"
                      value={principal}
                      onChange={(event) =>
                        editValue(setPrincipal, event.target.value)
                      }
                      min="0.01"
                      max="100000000"
                      step="0.01"
                      required
                      disabled={busy}
                    />
                  </Field>
                  <div className="form-grid">
                    <Field label="Annual interest rate (%)">
                      <input
                        className="input"
                        aria-label="Annual interest rate (%)"
                        type="number"
                        value={rate}
                        onChange={(event) =>
                          editValue(setRate, event.target.value)
                        }
                        min="0"
                        max="50"
                        step="0.01"
                        required
                        disabled={busy}
                      />
                    </Field>
                    <Field label="Term (months)">
                      <input
                        className="input"
                        aria-label="Term (months)"
                        type="number"
                        value={tenure}
                        onChange={(event) =>
                          editValue(setTenure, event.target.value)
                        }
                        min="1"
                        max="360"
                        step="1"
                        required
                        disabled={busy}
                      />
                    </Field>
                  </div>
                  {error && (
                    <div role="alert">
                      <Notice tone="danger">{error}</Notice>
                    </div>
                  )}
                  <Button type="submit" disabled={busy}>
                    {busy ? "Calculating…" : "Calculate monthly payment"}
                  </Button>
                  <p className="muted" style={{ fontSize: 12, margin: 0 }}>
                    Estimates use a fixed interest rate and exclude processing
                    fees, taxes, and changes in rates.
                  </p>
                </form>
                <div
                  style={{
                    background: "#f2f7f5",
                    borderRadius: 16,
                    padding: 24,
                    minHeight: 265,
                  }}
                  aria-live="polite"
                >
                  <div className="stat-label">Estimated monthly payment</div>
                  <div
                    className="metric-value"
                    style={{ fontSize: 38, margin: "14px 0", color: "#147858" }}
                  >
                    {calculation ? money(calculation.emi) : "—"}
                  </div>
                  {calculation ? (
                    <>
                      <div className="stack" style={{ gap: 14 }}>
                        <div className="row-between">
                          <span className="muted">Total interest</span>
                          <strong>{money(calculation.total_interest)}</strong>
                        </div>
                        <div className="row-between">
                          <span className="muted">Total repayment</span>
                          <strong>{money(calculation.total_payment)}</strong>
                        </div>
                      </div>
                      <div className="divider" />
                      <Notice
                        tone={calculation.affordable ? "success" : "warning"}
                      >
                        {calculation.affordable
                          ? "This estimated payment fits within the demo affordability threshold for your profile."
                          : "This estimated payment exceeds the demo affordability threshold. Consider a smaller amount or a longer term."}
                      </Notice>
                    </>
                  ) : (
                    <p className="muted">
                      Calculate a plan to see its full cost and how it compares
                      with your current budget.
                    </p>
                  )}
                </div>
              </div>
            </Card>
          </section>
          <div className="row-between">
            <div>
              <h2 className="section-title" style={{ fontSize: 22 }}>
                Protect what matters
              </h2>
              <p className="muted">
                Compare illustrative cover and understand eligibility at a
                glance.
              </p>
            </div>
            <span className="chip">Insurance options</span>
          </div>
          {recommendations.data.insurance.length ? (
            <div className="grid three">
              {recommendations.data.insurance.map((insurance) => (
                <Card key={insurance.id}>
                  <div className="row-between">
                    <span className="stat-label">Protection plan</span>
                    <StatusBadge
                      status={insurance.eligible ? "eligible" : "ineligible"}
                    />
                  </div>
                  <h3 style={{ fontSize: 20, margin: "16px 0" }}>
                    {insurance.name}
                  </h3>
                  <div className="metric-value">
                    {money(insurance.monthly_premium)}
                    <span
                      className="muted"
                      style={{ fontSize: 13, fontWeight: 400 }}
                    >
                      {" "}
                      / mo
                    </span>
                  </div>
                  <div className="muted">Illustrative monthly premium</div>
                  <div className="divider" />
                  <div className="row-between">
                    <span className="muted">Cover amount</span>
                    <strong>{money(insurance.cover)}</strong>
                  </div>
                  <div className="stat-label" style={{ marginTop: 22 }}>
                    Why this fits your profile
                  </div>
                  <ul
                    style={{ paddingLeft: 18, lineHeight: 1.65, fontSize: 14 }}
                  >
                    {insurance.reasons.map((reason, index) => (
                      <li key={index}>{reason}</li>
                    ))}
                  </ul>
                  <Button
                    variant={
                      compared.includes(insurance.id) ? "primary" : "secondary"
                    }
                    aria-pressed={compared.includes(insurance.id)}
                    onClick={() => toggleComparison(insurance.id)}
                    style={{ width: "100%" }}
                  >
                    {compared.includes(insurance.id)
                      ? "Remove from comparison"
                      : "Compare this cover"}
                  </Button>
                </Card>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No insurance recommendations available"
              description="Check back when your financial profile has been updated."
            />
          )}
          {coverComparison.length > 0 && (
            <Card>
              <div className="row-between">
                <div>
                  <h2 className="section-title">Your cover comparison</h2>
                  <p className="muted">
                    Review costs alongside cover. Full policy terms and
                    exclusions would apply to a real product.
                  </p>
                </div>
                <Button variant="ghost" onClick={() => setCompared([])}>
                  Clear comparison
                </Button>
              </div>
              <div className="table-wrap">
                <table className="data-table">
                  <caption className="sr-only">
                    Selected insurance plans
                  </caption>
                  <thead>
                    <tr>
                      <th>Plan</th>
                      <th>Monthly premium</th>
                      <th>Annual premium</th>
                      <th>Cover</th>
                      <th>Eligibility</th>
                    </tr>
                  </thead>
                  <tbody>
                    {coverComparison.map((insurance) => (
                      <tr key={insurance.id}>
                        <td>
                          <strong>{insurance.name}</strong>
                        </td>
                        <td>{money(insurance.monthly_premium)}</td>
                        <td>{money(Number(insurance.monthly_premium) * 12)}</td>
                        <td>{money(insurance.cover)}</td>
                        <td>
                          <StatusBadge
                            status={
                              insurance.eligible ? "eligible" : "ineligible"
                            }
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
          <p className="muted" style={{ fontSize: 13, textAlign: "center" }}>
            Recommendations explain your options; eligibility shown here is
            illustrative. Real products require lender or insurer review,
            verified information, and acceptance of their terms.
          </p>
        </>
      ) : (
        <EmptyState
          title="Your recommendations are not available"
          description="Try refreshing your profile."
        />
      )}
    </div>
  );
}
