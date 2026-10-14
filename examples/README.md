# Synthetic upload examples

All files here are test data and contain no real government identity evidence.

For the KYC screen upload `kyc/synthetic-id.png` and `kyc/synthetic-selfie.png`, with name **Aarav Sharma**, birth date **1994-05-12**, identity number **DEMO12345678**, country **India**. The local adapter validates evidence format and applies explicit demo checks; it does not verify liveness or identity. Production requires real KYC integrations.

Upload `sample-policy.txt` in Documents and ask “Why might a loan application be rejected?” The answer should cite the policy passages.
