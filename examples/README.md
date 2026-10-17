# Synthetic upload examples

All files here are test data and contain no real government identity evidence.

For the KYC screen upload `kyc/synthetic-id.png` and `kyc/synthetic-selfie.png`, with name **Aarav Sharma**, birth date **1994-05-12**, identity number **DEMO12345678**, country **India**. The local adapter validates evidence format and applies explicit demo checks; it does not verify liveness or identity. Production requires real KYC integrations.

Upload `sample-policy.txt` in Documents and ask “Why might a loan application be rejected?” The answer should cite the policy passages.

Use these on the [hosted demo](https://agies-bank.web.app) with **Customer demo**.
Identity decisions use the local synthetic adapter in the deployed project;
Gemini `gemini-3.1-flash-lite` is used for supported chat/document answers.
Inspect the recorded decision in Identity or
resolve a review case through **Analyst demo**. See the
[complete journey](../docs/END_TO_END.md) and [validation evidence](../docs/VALIDATION.md).

For banking education, open **Banking guides** without uploading a file. These
are original summaries linked to real RBI, DICGC, NPCI and Government of India
publications. Use **Explain with AI** to get an attributed answer. For planning,
ask **Create a goal for Emergency fund of INR 60000 in 12 months**, then review
and save the draft. See [AI workspace examples](../docs/AI_WORKSPACE.md).
