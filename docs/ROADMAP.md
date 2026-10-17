# Remaining work and future ideas

The Firestore-backed synthetic application is implemented and hosted. The
following are future extensions or production work, not features being claimed
as delivered. Current executed results are in [validation](VALIDATION.md).

## Practical product extensions

| Priority | Idea | Useful next increment |
| --- | --- | --- |
| 1 | Scanned-document OCR | Extract images locally or through an approved OCR service; keep page/excerpt provenance and upload bounds |
| 1 | Provider reliability and evaluations | Scheduled synthetic model probes, measured latency/error budgets and grounded-answer regression datasets |
| 1 | Opt-in notifications | Customer-controlled email/push for completed reviews and security alerts, with delivery receipts and unsubscribe |
| 2 | Multilingual/voice assistant | Hindi and other language UI/audio; display the exact recipient/amount in the confirmation dialog |
| 2 | Semantic retrieval | Embeddings and Firestore vector retrieval, retaining tenant filters and source validation |
| 2 | Explainable anomaly feedback | Analyst-labelled outcomes, model evaluation and monitored drift alongside deterministic risk gates |
| 2 | Richer planning | Recurring-expense planning, what-if cash-flow scenarios and goal simulations without automatic payments |
| 3 | Regulatory/reporting assistant | Reviewable report drafts from approved records, source links and human sign-off |

## Scale and release engineering

Collection-wide revision guards preserve this prototype's correctness but can
create contention. Partition guards by tenant/account, maintain tested aggregate
projections, bound global analyst queries and load-test hot accounts before
expanding scale. Keep paired financial writes atomic during that change.

Add an isolated staging project, canary traffic, automated rollback of compatible
app revisions and release attestations. Current delivery validates `main`, uses
keyless identity and runs hosted smoke checks; it does not claim a staged canary
or automatic database rollback. Track application, worker, scheduler and provider
errors, and configure budget alerts, exports/PITR and tested restores.

## Real financial operations

Real money requires contracted bank/payment APIs, signed and idempotent webhooks,
settlement/reconciliation protocols, dispute handling and sandbox certification.
Replace synthetic KYC/liveness, sanctions, bureau and attested device/location
feeds with approved provider integrations. Enroll a real MFA factor rather than
the current demo password challenge. Complete jurisdiction-specific legal,
privacy, consent, retention and operational reviews before real customer use.

The historical 99-row SQLite database was not supplied and is not in the hosted
demo. If it becomes available, preserve it, import into an isolated empty target
and use the [offline cutover](CLOUD_SETUP.md) procedure. Do not overlay it on the
seeded demonstration or repair balances from model output.
