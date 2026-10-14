# Saved cloud configuration

The cloud draft contains these tested fields:

- `install_script`: change directory to `/workspace/agies-bank` and run `bash scripts/setup.sh`, installing hash-verified Python and npm-lock dependencies.
- `start_skill`: use the existing isolated checkout, inspect occupied ports, start `bash scripts/dev.sh`, verify health and authenticated banking responses, preserve retained data and respect supplied configuration. The repository's current startup instructions cover local mode, optional Claude/OpenAI capabilities, durable financial-health jobs and operational limitations.

The machine supports the synthetic development workflow. A saved draft does not execute installation, activate runtime settings, publish a snapshot or prove restoration in a new task. Repository documentation edits do not themselves update platform draft fields. Review and save the current draft in environment settings, then publish the environment when ready.

No required secret or network change was needed for local mode. For optional Claude, supply `ANTHROPIC_API_KEY` securely and allow `api.anthropic.com`; for OpenAI, supply `AEGIS_OPENAI_API_KEY` and allow `api.openai.com`. The root `.env` is ignored by Git and read through a variable allowlist without shell execution. Existing injected variables take precedence. Use the `AEGIS_OPENAI_API_KEY` binding in Codex cloud settings; `OPENAI_API_KEY` is a local alias and can be a reserved platform target.

With `AEGIS_AI_PROVIDER=auto`, one supplied key selects its provider; when both are present, Claude is preferred. Select `claude`, `openai` or `local` explicitly when required. `AEGIS_KYC_VISION` independently controls optional evidence-quality assistance. Restart the backend after configuration changes. Provider credentials also need account permissions, accessible models, credits and working network access. Model-access checks in the analyst Integrations page do not send customer data or validate paid inference. Never enter credentials in chat or source control.

Only the implemented AI adapters are key-ready. Bank settlement, legal identity/liveness, sanctions, bureau, GeoIP/device attestation and production MFA still need provider-specific integrations. An AI key does not activate those services. Model vision can assess submitted evidence quality; it cannot prove document authenticity or legal identity.

Development startup creates local tables; production requires an explicit migration job to the current Alembic head, including `0002_proactive`. Agent runs and planning goals are database records and survive API restarts. The worker restarts with the API and can recover expired leases; it does not move funds or approve identity. Saved goal progress is manually recorded planning data, never earmarked money.

Running processes and Docker containers must restart after restoration. Each cloud task is isolated; use the existing checkout rather than creating a Git worktree.
