# API contract (v1)

All paths below are prefixed `/api`. API errors use HTTP errors with a readable `detail`. Session auth uses HttpOnly cookie `__session`. Client fetch uses credentials and for non-GET requests sends `X-CSRF-Token` from login/session responses. Development frontend proxies `/api` to backend on 8000. JSON responses use snake_case. Amounts are INR decimal strings; requests can send decimal strings/numbers, API uses integer paise internally. Synthetic demo users: `customer@aegis.demo` / `AegisDemo!2026` and `analyst@aegis.demo` / `AegisAnalyst!2026`.

## Authentication

- `GET /health` -> `{status, database, storage, ai_mode, demo_enabled, ...}`; `storage` is `firestore` in hosted mode.
- `POST /auth/login {email,password}` -> `{user:{id,name,email,role},csrf_token}`
- `POST /auth/register {name,email,password}` -> same; creates zero-balance account, not free money.
- `GET /auth/me` -> same.
- `POST /auth/logout` -> `{ok:true}`

## Customer

- `GET /overview` -> `{user,account:{id,number,balance,currency,status,kyc_status},spending:{income,expenses,savings_rate,categories:[{category,amount}]},transactions:[...],alerts:[...],budgets:[...],agent_activity:[...]}`
- `GET /transactions` -> list `{id,amount,direction,description,category,status,created_at,balance_after}`; status includes posted/held/rejected/pending_step_up.
- `GET /beneficiaries` -> `[{id,name,bank,account_last4,is_new}]`; `POST /beneficiaries {name,bank,account_number}` -> same.
- `POST /transfers {beneficiary_id,amount,description,idempotency_key}` -> `{id,status,risk_score,signals:[{name,score,detail}],decision,case_id?,message}`. Server derives device/IP context from recent events; client cannot downgrade risk through supplied context.
- `POST /transfers/{id}/step-up {password}` -> transfer. Server-password challenge stands in for production MFA and is labelled as such.
- `POST /alerts/{id}/respond {recognized:boolean}` -> alert.
- `GET /events` -> recent login events `[{id,kind,city,country,latitude,longitude,ip_masked,device,is_new_device,vpn,risk_score,signals,created_at}]`.
- `POST /simulator/events {scenario}` scenario = `routine_login`, `impossible_travel`, `vpn_login`, `large_transfer`, `velocity_burst`; -> `{event?,transfer?,case?,message}`. Demo only; disabled in production.
- `GET /budgets` -> `[{id,category,limit_amount,spent}]`; `PUT /budgets/{category} {limit_amount}` -> budget.
- `POST /chat {message}` -> `{reply,agent,tools:[{name,summary}],citations:[{document_id,title,excerpt,page}],proposal?:{beneficiary_id,amount,description},trace_id}`. Proposal needs explicit customer submission to /transfers. `GET /chat` -> history `[{id,role,content,agent,created_at}]`.
- `GET /recommendations` -> `{profile:{monthly_income,monthly_expenses,credit_score,age},loans:[{id,name,rate,tenure_months,max_amount,eligible,reasons,emi}],insurance:[{id,name,monthly_premium,cover,eligible,reasons}],disclaimer}`.
- `POST /recommendations/calculate {principal,annual_rate,tenure_months}` -> `{emi,total_interest,total_payment,affordable}`.
- `GET /kyc` -> `{status,submissions:[{id,status,risk_score,reasons,document_name,created_at}],disclaimer}`.
- `POST /kyc` multipart `{full_name,date_of_birth,id_number,country,document:File,selfie:File}` -> submission with decision.
- `GET /documents` -> list `{id,title,kind,filename,chunk_count,created_at}`.
- `POST /documents` multipart `{file,title?}` -> document.
- `POST /documents/query {question,document_id?}` -> `{answer,citations:[{document_id,title,excerpt,page}],agent,trace_id}`.
- `GET /audit` -> list `{id,agent,action,summary,risk_score?,tools,created_at,trace_id}` scoped to current customer.

## Analyst

- `GET /analyst/overview` -> `{metrics:{open_cases,held_amount,kyc_pending,frozen_accounts},cases:[...],recent_audit:[...]}`.
- `GET /analyst/cases` -> list `{id,kind,status,priority,customer_name,customer_id,risk_score,amount,summary,signals,created_at,transfer_id?,kyc_id?}`.
- `GET /analyst/cases/{id}` -> `{case,customer:{id,name,email},account,events:[...],audit:[...]}`.
- `POST /analyst/cases/{id}/resolve {decision:'approve'|'reject',reason}` -> case. Only pending items can resolve; operations atomic, balances rechecked.
- `GET /analyst/customers` -> list `{id,name,email,account_id,account_status,balance,kyc_status}`.
- `POST /analyst/accounts/{id}/status {status:'active'|'frozen',reason}` -> account; audited.
- `GET /analyst/audit` -> audit across customers, masking PII and excluding secrets.

Paginate/limit stored history in backend; consistent default arrays for empty results. API docs at `/docs`. Web routes `/`, `/login`, `/dashboard`, `/assistant`, `/documents`, `/kyc`, `/payments`, `/recommendations`, `/security`, `/activity`, `/analyst`, `/analyst/cases`, `/analyst/customers`, `/analyst/audit`. Customer app exposes logout. Analyst shell isolates role navigation.

## Proactive guidance, planning and integration extensions

- `GET /insights` -> `{items:[{id,kind,severity,title,message,action_label,action_path,status,metrics,created_at,updated_at}],summary:{...},latest_run}`; initial summary may be empty while a durable run is queued.
- `POST /insights/refresh` -> AgentRun, HTTP202; coalesces pending work and permits a fresh review after completion.
- `GET /notifications/agents` -> `{source:'database'|'firestore',items:[...]}` scoped to the signed-in customer. `database` means the authoritative application repository, which is Firestore in hosted mode. An optional separate Firestore notification projection may serve derived alerts; projection failure falls back to authoritative Firestore records. There is no SQL fallback.
- `POST /insights/{id}/dismiss` -> insight; only the owning customer can dismiss it.
- `GET /agent-runs` -> owned run list with status, attempts, max_attempts, tools, decisions, trace_id, output, error and timestamps. Jobs are read-only financial reviews, never transfer execution.
- `POST /agent-runs/{id}/retry` -> AgentRun, HTTP202; only failed owned runs, bounded manual retries.
- `GET /goals` -> owned SavingsGoal list.
- `POST /goals {name,target_amount,saved_amount?,target_date?}` -> goal, HTTP201.
- `PATCH /goals/{id} {name?,target_amount?,saved_amount?,target_date?,status?}` -> goal; active/paused/completed states.
- `DELETE /goals/{id}` -> `{deleted:true}`. These are planning records; all create/update/delete operations preserve ledger entries and account balances.
- `GET /documents/{id}/content` -> `{document,pages:[{page,text}]}`: exact indexed source passages, customer/private or shared policy only. Long pages may include overlapping chunks.
- `GET /analyst/integrations` -> `{ai_mode,kyc_mode,providers:[{id,name,status,integrated,mode,credential_configured,model,model_selection,endpoints,capabilities,limitations,requirements}],firestore:{agent_notifications_enabled,project_configured,database},disclaimer}`. Credential values never appear.
- `POST /analyst/integrations/{claude|openai|gemini|openrouter}/check` -> `{status,configured,model,checked_at,message,error_code?,scope}`. Non-destructive provider/model-catalog check; it does not prove inference availability or real financial operations.
- `GET /analyst/documents` -> shared bank policies only.
- `POST /analyst/documents` multipart `{file,title,confirmed_public:true}` -> shared policy, HTTP201. Analyst role, valid CSRF and explicit public-sharing confirmation required. This publishes Q&A knowledge; it does not change lending/payment policy rules.

Web routes added: `/insights` and `/analyst/integrations`. All mutation endpoints require session auth and `X-CSRF-Token`; CORS explicitly supports PATCH/DELETE for planning operations.


## Firestore workflows and operations

| Method | Path | Scope / behavior |
| --- | --- | --- |
| GET | `/automations` | Customer workflow catalog and own schedules |
| PUT | `/automations` | Upsert own `{kind, interval_hours, enabled}` schedule; 1–168 hours |
| POST | `/automations/{id}/run` | Queue enabled owned workflow; returns 202 and run |
| DELETE | `/automations/{id}` | Remove own schedule; retain prior jobs/audit |
| GET | `/analyst/operations` | Analyst-only ledger reconciliation and job/lease counts |

Kinds: `financial_health`, `security_review`, `document_review`, `savings_coach`.
These workflows produce read-only guidance. Pausing does not cancel an already
queued job. Mutation routes require session CSRF and Origin checks. Unknown
workflow kinds, invalid intervals and extra fields are rejected. Foreign schedule
IDs return 404. A bounded optimistic conflict returns a retryable 409 without
partial writes; clients must retain the transfer idempotency key when retrying.
`/health` reports the actual storage adapter. Hosted cookies use Secure HttpOnly
`__session` to pass through Firebase Hosting; session values never appear in logs.
Document uploads are bounded to 300 extracted chunks per atomic write.

Chat and document-query responses include `ai_mode`, reporting the provider
actually used for the answer. An OpenRouter rate limit, transient server failure
or network timeout returns a scoped local answer with `ai_mode:'local'`,
`fallback_from:'openrouter'` and a visible notice in `reply`/`answer`. Local
document answers retain exact accessible excerpts/citations. Provider credential
or configuration errors, malformed answers, invalid citations and missing
required tools continue to return an error. The assistant's provider loop has a
40-second budget within the hosted gateway's 55-second proxy window.

A successful OpenRouter `propose_transfer` tool returns server-authored consent
text. Model prose cannot claim settlement or add stale document citations to the
proposal. `POST /transfers` remains the separate, idempotent confirmation action;
the proposal itself changes no balances or ledger entries.
