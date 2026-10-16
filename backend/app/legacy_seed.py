from datetime import timedelta
from sqlalchemy import select
from .legacy_models import *
from .auth import hash_password
from .services.workflows import account_hash
def audit(db, user_id, agent, action, summary, tools):
    db.add(AuditLog(user_id=user_id, agent=agent, action=action, summary=summary, tools=tools))


def seed_demo(db):
    clearing = db.scalar(select(Account).where(Account.number == "INTERNAL_CLEARING"))
    if not clearing:
        clearing = Account(
            number="INTERNAL_CLEARING",
            user_id=None,
            balance_paise=0,
            status="active",
            kyc_status="approved",
        )
        db.add(clearing)
        db.flush()
    if db.scalar(select(User).where(User.email == "customer@aegis.demo")):
        return
    customer = User(
        name="Satyam Sahu",
        email="customer@aegis.demo",
        role="customer",
        password_hash=hash_password("AegisDemo!2026"),
    )
    analyst = User(
        name="Priya Nair",
        email="analyst@aegis.demo",
        role="analyst",
        password_hash=hash_password("AegisAnalyst!2026"),
    )
    db.add_all([customer, analyst])
    db.flush()
    account = Account(
        user_id=customer.id,
        number="AEGIS10004821",
        balance_paise=0,
        status="active",
        kyc_status="approved",
    )
    db.add(account)
    db.flush()
    rows = [
        (18_000_000, "credit", "Opening savings (synthetic)", "savings", 45),
        (9_500_000, "credit", "Salary · Acme Technologies", "salary", 8),
        (2_800_000, "debit", "October rent", "housing", 7),
        (1_482_050, "debit", "FreshMart groceries", "groceries", 5),
        (385_000, "debit", "Dining & cafes", "dining", 3),
        (184_900, "debit", "Electricity and internet", "utilities", 2),
        (100_000, "debit", "Streaming and software", "subscriptions", 1),
    ]
    for amount, direction, description, category, days in rows:
        delta = amount if direction == "credit" else -amount
        account.balance_paise += delta
        clearing.balance_paise -= delta
        created = utcnow() - timedelta(days=days)
        db.add_all(
            [
                LedgerEntry(
                    account_id=account.id,
                    amount_paise=amount,
                    direction=direction,
                    description=description,
                    category=category,
                    balance_after_paise=account.balance_paise,
                    created_at=created,
                ),
                LedgerEntry(
                    account_id=clearing.id,
                    amount_paise=amount,
                    direction="debit" if direction == "credit" else "credit",
                    description="Synthetic seed counterpart",
                    category="settlement",
                    balance_after_paise=clearing.balance_paise,
                    created_at=created,
                ),
            ]
        )
    db.add_all(
        [
            Beneficiary(
                user_id=customer.id,
                name="Ananya Sharma",
                bank="HDFC Bank",
                account_last4="4821",
                account_number_hash=account_hash("501000004821"),
                is_new=False,
            ),
            Beneficiary(
                user_id=customer.id,
                name="Rahul Mehta",
                bank="ICICI Bank",
                account_last4="9034",
                account_number_hash=account_hash("810000009034"),
                is_new=False,
            ),
            Budget(user_id=customer.id, category="groceries", limit_paise=2_000_000),
            Budget(user_id=customer.id, category="dining", limit_paise=500_000),
            Budget(user_id=customer.id, category="housing", limit_paise=3_000_000),
        ]
    )
    db.add(
        KYCSubmission(
            user_id=customer.id,
            full_name=customer.name,
            date_of_birth="1995-06-15",
            id_last4="4321",
            country="IN",
            status="approved",
            risk_score=5,
            reasons=[
                "Synthetic demo identity pre-verified. No live identity provider used."
            ],
            document_name="Synthetic demo identity",
            document_hash="synthetic",
            selfie_hash="synthetic",
        )
    )
    docs = [
        (
            None,
            "Aegis Personal Loan Policy",
            "policy",
            "loan-policy.txt",
            [
                "Aegis Personal Loan Policy. Eligible applicants are resident Indian adults aged 21 to 60 with monthly income of at least INR 25,000 and an indicative credit score of 700. All eligibility estimates are synthetic and require formal underwriting.",
                "Personal loan interest rates start at 10.5% annually. Tenures range from 12 to 60 months. Maximum recommended EMI must not exceed 35% of monthly disposable income. No loan is issued automatically. Processing fees may apply and an exact offer requires a lender quote.",
                "Early repayment is permitted under the signed loan agreement. A 14-day cooling-off period is available for eligible digital lending products. Contact the bank for the final sanction letter and terms.",
            ],
        ),
        (
            None,
            "Aegis Term Life Insurance Policy",
            "policy",
            "insurance-policy.txt",
            [
                "Aegis Term Life policy provides a death benefit of INR 10,000,000 for eligible applicants aged 18 to 55. Indicative monthly premium starts at INR 850 and is subject to health, occupation and insurer underwriting.",
                "Term life insurance does not accumulate cash value. The standard waiting period for suicide exclusions is 12 months from inception or revival. A free-look period of 30 days permits policy review and cancellation subject to applicable terms.",
                "Insurance eligibility estimates use synthetic assumptions. This tool is educational and is not a binding insurance offer. Final cover and exclusions depend on the insurer policy schedule.",
            ],
        ),
        (
            customer.id,
            "October Account Statement",
            "statement",
            "october-statement.txt",
            [
                "Synthetic AegisBank October Account Statement for Satyam Sahu. Account ending 4821. Salary received INR 95,000. Opening savings INR 180,000. Closing available balance INR 225,480.50.",
                "Statement transactions: Rent INR 28,000; groceries INR 14,820.50; dining INR 3,850; utilities INR 1,849; subscriptions INR 1,000. Total monthly spending INR 49,519.50. All records are synthetic demo data.",
            ],
        ),
    ]
    for user_id, title, kind, filename, pages in docs:
        doc = Document(user_id=user_id, title=title, kind=kind, filename=filename)
        db.add(doc)
        db.flush()
        for page, text in enumerate(pages, 1):
            db.add(DocumentChunk(document_id=doc.id, text=text, page=page))
    audit(
        db,
        customer.id,
        "orchestrator",
        "demo_initialized",
        "Synthetic customer, ledger and policy documents initialized; no real provider connections",
        ["mock_core", "mock_kyc", "policy_documents"],
    )
    db.commit()
