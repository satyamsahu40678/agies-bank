import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronRight,
  Fingerprint,
  Globe,
  LockKeyhole,
  Shield,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import { Brand } from "@/components/app-shell";
export default function Home() {
  return (
    <div className="landing">
      <header className="landing-nav">
        <Link href="/" aria-label="AegisBank home">
          <Brand />
        </Link>
        <nav aria-label="Website navigation">
          <a href="#intelligence">Intelligent banking</a>
          <a href="#protection">Built-in protection</a>
          <Link href="/login">Sign in</Link>
        </nav>
        <Link href="/register" className="button button-primary">
          Open your account <ArrowUpRight size={15} />
        </Link>
      </header>
      <main>
        <section className="landing-hero">
          <div className="hero-copy">
            <div className="hero-tag">
              <span className="pulse-dot" />
              MEET YOUR NEXT CHAPTER
            </div>
            <h1>
              Your money.
              <br />A little smarter.
              <br />
              <span>A lot more secure.</span>
            </h1>
            <p>
              A banking experience that thinks ahead. Five specialist agents
              help you manage, understand, and protect your money—with you in
              control.
            </p>
            <div className="hero-buttons">
              <Link href="/login" className="button button-primary">
                Explore the live demo <ArrowRight size={17} />
              </Link>
              <Link href="/register" className="button button-secondary">
                Create an account
              </Link>
            </div>
            <div className="hero-trust">
              <ShieldCheck size={17} />
              <span>Governed decisions</span>
              <i />
              <span>Transparent by design</span>
            </div>
          </div>
          <div className="hero-visual">
            <div className="visual-orbit orbit-one" />
            <div className="visual-orbit orbit-two" />
            <div className="hero-bank-card">
              <div className="row-between">
                <Brand />
                <span className="hero-card-type">PERSONAL</span>
              </div>
              <div className="hero-balance-label">TOTAL AVAILABLE BALANCE</div>
              <div className="hero-balance">
                ₹2,25,480<span>.50</span>
              </div>
              <div className="hero-account-dots">
                •••• &nbsp; •••• &nbsp; •••• &nbsp; 4821
              </div>
              <div className="row-between">
                <div className="hero-card-name">AARAV SHARMA</div>
                <div className="hero-card-chip">
                  <i />
                  <i />
                  <i />
                </div>
              </div>
            </div>
            <div className="hero-assistant-card">
              <span className="ai-orb">
                <Sparkles size={20} />
              </span>
              <div>
                <strong>Ahead of the unexpected.</strong>
                <p>
                  Your security agent flagged an unusual login.
                  <br />
                  Your account is protected.
                </p>
                <span>
                  <ShieldCheck size={12} />
                  Risk evaluated · Action explained
                </span>
              </div>
              <span className="assistant-card-dot" />
            </div>
            <div className="hero-savings-card">
              <div>
                <span>THIS MONTH</span>
                <strong>A clearer financial picture.</strong>
              </div>
              <svg
                viewBox="0 0 180 55"
                role="img"
                aria-label="Illustrative rising savings trend"
              >
                <defs>
                  <linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1">
                    <stop stopColor="#a9d7b6" stopOpacity=".5" />
                    <stop offset="1" stopColor="#a9d7b6" stopOpacity="0" />
                  </linearGradient>
                </defs>
                <path
                  d="M2 47L24 41L42 45L65 28L82 32L102 19L123 24L143 9L164 13L178 4V55H2Z"
                  fill="url(#chartFill)"
                />
                <path
                  d="M2 47L24 41L42 45L65 28L82 32L102 19L123 24L143 9L164 13L178 4"
                  fill="none"
                  stroke="#79aa86"
                  strokeWidth="2.5"
                />
              </svg>
            </div>
            <div className="visual-caption">
              <LockKeyhole size={12} />
              Illustrative synthetic demo account
            </div>
          </div>
        </section>
        <section className="landing-values">
          <div>
            <span>01</span>
            <strong>One intelligent workspace</strong>
            <p>Every account. Every insight. One place.</p>
          </div>
          <div>
            <span>02</span>
            <strong>Five focused specialists</strong>
            <p>Your money, understood from every angle.</p>
          </div>
          <div>
            <span>03</span>
            <strong>You make the final call</strong>
            <p>Every payment needs your explicit approval.</p>
          </div>
        </section>
        <section className="landing-section" id="intelligence">
          <div className="row-between">
            <div>
              <p className="eyebrow">LESS FRICTION. MORE CLARITY.</p>
              <h2>
                Banking that meets you
                <br />
                where you are.
              </h2>
            </div>
            <p className="section-intro">
              Get answers, make thoughtful decisions, and see exactly why your
              bank takes action.
            </p>
          </div>
          <div className="grid three landing-feature-grid">
            <article>
              <div className="landing-feature-icon">
                <Sparkles />
              </div>
              <h3>A personal banking copilot</h3>
              <p>
                Ask about your balance, discover spending patterns, or prepare a
                payment. Your assistant connects the dots and explains the next
                step.
              </p>
              <Link href="/login">
                Meet your assistant <ArrowUpRight size={15} />
              </Link>
            </article>
            <article>
              <div className="landing-feature-icon">
                <Globe />
              </div>
              <h3>A better view of your money</h3>
              <p>
                Track spending, set meaningful budgets, and explore loan and
                insurance options with clear eligibility reasons and real
                repayment estimates.
              </p>
              <Link href="/login">
                Explore your workspace <ArrowUpRight size={15} />
              </Link>
            </article>
            <article>
              <div className="landing-feature-icon">
                <Fingerprint />
              </div>
              <h3>Protection with perspective</h3>
              <p>
                Risk signals, identity checks, and human review work together.
                Unusual activity is held for a thoughtful, auditable decision.
              </p>
              <Link href="/login">
                See security in action <ArrowUpRight size={15} />
              </Link>
            </article>
          </div>
        </section>
        <section className="landing-protection" id="protection">
          <div>
            <p className="eyebrow">TRUST IS A SYSTEM.</p>
            <h2>
              Every decision.
              <br />
              Out in the open.
            </h2>
            <p>
              From an assistant suggestion to an analyst review, follow the
              evidence, tools, and actions in a transparent audit trail.
            </p>
            <Link href="/login" className="button button-secondary">
              Explore the analyst console <ChevronRight size={16} />
            </Link>
          </div>
          <div className="protection-list">
            {[
              {
                icon: Shield,
                title: "Policy before action",
                copy: "Risk controls govern every transfer, regardless of who proposes it.",
              },
              {
                icon: Check,
                title: "Human decisions that matter",
                copy: "High-risk transfers and identity cases require an analyst review.",
              },
              {
                icon: LockKeyhole,
                title: "Your workspace stays yours",
                copy: "Authenticated sessions and scoped tools keep customer data isolated.",
              },
            ].map((item) => (
              <div key={item.title}>
                <span>
                  <item.icon size={20} />
                </span>
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.copy}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
        <section className="landing-disclaimer">
          <ShieldCheck size={18} />
          <div>
            <strong>Built to demonstrate the future. Clear about today.</strong>
            <p>
              AegisBank is a functional synthetic banking sandbox. Core banking,
              identity, sanctions, and credit bureau providers are simulated.
              The local AI mode needs no API key. No real deposits, payments, or
              financial products are issued.
            </p>
          </div>
        </section>
      </main>
      <footer className="landing-footer">
        <Brand />
        <span>Intelligence with accountability.</span>
        <Link href="/login">
          Enter the workspace <ArrowRight size={14} />
        </Link>
      </footer>
    </div>
  );
}
