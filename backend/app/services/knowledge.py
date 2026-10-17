"""Versioned educational summaries of primary Indian banking sources.

Original summaries, not copies of regulations. Shipping these with the release
keeps retrieval reproducible without a runtime crawler or remote database writes.
"""

from fastapi import HTTPException

REVIEWED_AT = "2026-10-17"
NOTICE = "Educational summaries for India. Check the linked authority and your bank for current requirements. AegisBank is a demo, not an insured bank or a regulated financial provider."

GUIDES = [
    {
        "id": "guide-deposit-insurance",
        "title": "How deposit insurance works",
        "category": "Deposits",
        "publisher": "DICGC",
        "source_url": "https://www.dicgc.org.in/FAQs",
        "summary": "Understand the insurance ceiling and why multiple accounts do not necessarily mean more cover.",
        "content": "## Deposit insurance in India\n\nDICGC covers eligible deposits at insured banks up to **₹5 lakh per depositor per bank**, including principal and interest, in the same right and capacity. Deposits across branches of the same bank are combined for this purpose. Opening several accounts at that bank does not multiply this limit.\n\n### What to check\n\n- Confirm that the institution is an insured bank.\n- Consider principal and accrued interest together.\n- Check how ownership and account capacity affect aggregation.\n- Consult DICGC's FAQ for exclusions, set-off and claim rules.\n\nThis describes real insured banks. The sample balances in AegisBank are synthetic and have no deposit insurance.",
        "questions": ["How does the ₹5 lakh deposit insurance limit work?", "Are deposits at different branches combined?"],
    },
    {
        "id": "guide-upi-safety",
        "title": "UPI payments and PIN safety",
        "category": "Payments",
        "publisher": "NPCI",
        "source_url": "https://www.npci.org.in/what-we-do/upi/faqs",
        "summary": "Understand UPI, protect your PIN, and find the right place to raise a payment issue.",
        "content": "## UPI essentials\n\nUPI is an instant payment system developed by NPCI. It supports payments around the clock. A UPI PIN authorizes payments; keep it private. Your bank's support team should never ask you to disclose it.\n\n### Before and after paying\n\n- Check the recipient and amount before authorizing.\n- Use your bank or participating UPI app to raise a transaction complaint.\n- Keep the transaction reference and check its status before trying again.\n- If a phone is lost, contact your bank and mobile provider promptly.\n\nLimits, supported features and resolution procedures can depend on the payment type, app and bank. Read the current NPCI guidance and your bank's terms. AegisBank demonstrates transfers but does not connect to UPI.",
        "questions": ["What is UPI and should I share my UPI PIN?", "Where can I raise a UPI transaction complaint?"],
    },
    {
        "id": "guide-neft",
        "title": "NEFT: how bank transfers are processed",
        "category": "Payments",
        "publisher": "Reserve Bank of India",
        "source_url": "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=11750",
        "summary": "Learn why a NEFT transfer is processed in batches even though the system is available all day.",
        "content": "## NEFT processing\n\nRBI made NEFT available **24 hours a day, every day**, including holidays. The system operates in 48 half-hourly settlement batches. This means availability around the clock does not make every transfer instantaneous.\n\nRBI's direction requires credit to the beneficiary, or return to the originating bank, within two hours of settlement of the relevant batch. Keep your transfer reference and contact your bank about an unresolved payment.\n\nCheck recipient account details carefully and use your bank's current fees, channel limits and service instructions. AegisBank does not submit payments to the real NEFT system.",
        "questions": ["Is NEFT available on holidays?", "How do NEFT settlement batches work?"],
    },
    {
        "id": "guide-rtgs",
        "title": "RTGS: large-value transfers",
        "category": "Payments",
        "publisher": "Reserve Bank of India",
        "source_url": "https://www.rbi.org.in/scripts/FS_FAQs.aspx?Id=65",
        "summary": "Compare real-time settlement with batch processing and understand the minimum transfer amount.",
        "content": "## RTGS essentials\n\nRTGS settles transfers individually in real time rather than in batches. RBI's FAQ describes a **₹2 lakh minimum** and no RBI-imposed maximum. The system is available 24×7×365. Your bank can have its own channel controls and service terms.\n\nRTGS settlement in RBI's books is final and irrevocable, so verify the recipient account and amount before authorizing a payment. Contact your bank for transaction tracking or a problem; do not assume a completed payment can simply be cancelled.\n\nAegisBank's sample transfers are a separate demo and do not use RBI settlement infrastructure.",
        "questions": ["What is the minimum amount for RTGS?", "How is RTGS different from NEFT?"],
    },
    {
        "id": "guide-rekyc",
        "title": "Keeping your KYC details current",
        "category": "Identity",
        "publisher": "Reserve Bank of India",
        "source_url": "https://rbikehtahai.rbi.org.in/RBIREKYC.html",
        "summary": "Understand the difference between unchanged details and an update to your identity information.",
        "content": "## Re-KYC preparation\n\nRBI's customer-awareness guidance explains that, when KYC details have not changed, a self-declaration can be submitted through supported bank channels, including registered contact channels or a business correspondent.\n\nWhen details have changed, the guidance asks for a copy of an accepted document showing the updated details. It lists Aadhaar, voter ID, NREGA job card, driving licence, passport and a National Population Register letter. A branch visit is another route.\n\nConfirm your bank's procedure and use its verified channels. Do not send identity documents, OTPs or credentials to the chatbot. AegisBank's identity workflow uses demo checks and does not establish regulatory KYC compliance.",
        "questions": ["What if my KYC details have not changed?", "How can I update changed KYC details?"],
    },
    {
        "id": "guide-complaints",
        "title": "Bank complaints and the RBI Ombudsman",
        "category": "Consumer rights",
        "publisher": "Department of Financial Services, Government of India",
        "source_url": "https://financialservices.gov.in/banking",
        "summary": "Know where to start a complaint and when the integrated ombudsman mechanism may help.",
        "content": "## Resolving a banking complaint\n\nStart with the regulated financial institution's complaint process and keep its acknowledgement, transaction reference, dates and response.\n\nThe Government of India's banking guidance describes RBI's Integrated Ombudsman Scheme as a cost-free mechanism for complaints about deficiencies in service by covered regulated entities when the complaint is not resolved satisfactorily or the entity has not replied within 30 days.\n\nCheck the current scheme for eligibility, exclusions and filing deadlines. RBI's official Complaint Management System is at **https://cms.rbi.org.in/**. Never publish account credentials or private identity documents in a public complaint. AegisBank does not file complaints with RBI or represent a regulated bank.",
        "questions": ["When can I approach the RBI Ombudsman?", "What should I keep when raising a bank complaint?"],
    },
]


def list_guides():
    return [{**guide, "reviewed_at": REVIEWED_AT, "jurisdiction": "India", "notice": NOTICE} for guide in GUIDES]


def get_guide(guide_id):
    for guide in list_guides():
        if guide["id"] == guide_id:
            return guide
    raise HTTPException(404, "Banking guide not found.")
