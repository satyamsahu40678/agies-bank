import {
  test,
  expect,
  Page,
} from "../../frontend/node_modules/@playwright/test";
import path from "node:path";

const repo = path.resolve(__dirname, "../..");
async function customer(page: Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: "Customer demo" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}
async function analyst(page: Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: "Analyst demo" }).click();
  await expect(page).toHaveURL(/\/analyst$/);
}
test("customer can review and confirm a payment with a real ledger result", async ({
  page,
}) => {
  await customer(page);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.screenshot({
    path: path.join(repo, "test-results/customer-dashboard.png"),
    fullPage: true,
  });
  await page.goto("/payments");
  await page
    .getByLabel("Recipient", { exact: true })
    .selectOption({ index: 1 });
  await page.getByLabel("Amount (INR)", { exact: true }).fill("1.00");
  await page
    .getByLabel("Payment description", { exact: true })
    .fill("Browser acceptance payment");
  const before = Number(
    (await (await page.request.get("/api/overview")).json()).account.balance,
  );
  await page.getByRole("button", { name: "Review transfer" }).click();
  const settlement = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/transfers") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Confirm transfer" }).click();
  const result = await settlement;
  expect(result.ok()).toBeTruthy();
  expect((await result.json()).status).toBe("posted");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  expect(
    before -
      Number(
        (await (await page.request.get("/api/overview")).json()).account
          .balance,
      ),
  ).toBe(1);
  const response = await page.request.get("/api/transactions");
  expect(response.ok()).toBeTruthy();
  expect(
    (await response.json()).some(
      (t: { description: string }) =>
        t.description === "Browser acceptance payment",
    ),
  ).toBeTruthy();
});

test("document upload answers a question with an exact source citation", async ({
  page,
}) => {
  await customer(page);
  await page.goto("/documents");
  await page.getByRole("button", { name: "Upload document" }).click();
  await page.getByLabel("Document title").fill("Browser continuity policy");
  await page
    .getByLabel("Document file")
    .setInputFiles({
      name: "continuity.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(
        "The customer continuity code is PINE-204. The policy requires analyst approval for high risk transfers.",
      ),
    });
  await page.getByRole("button", { name: "Upload and index" }).click();
  await expect(
    page.getByRole("button", { name: /Browser continuity policy/ }),
  ).toBeVisible();
  await page
    .getByLabel("Ask about this document")
    .fill("What is the customer continuity code?");
  await page.getByRole("button", { name: "Ask document" }).click();
  await expect(
    page.getByRole("heading", { name: "Your answer" }),
  ).toBeVisible();
  await expect(page.locator("blockquote")).toContainText("PINE-204");
});

test("KYC submits sample identity evidence and renders a persisted decision", async ({
  page,
}) => {
  await page.goto("/register");
  await page.getByLabel("Full name").fill("Aarav Sharma");
  await page
    .getByLabel("Email address")
    .fill(`browser-${Date.now()}@example.test`);
  await page
    .getByLabel("Password", { exact: false })
    .first()
    .fill("BrowserAccount!2026");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.goto("/kyc");
  await page.getByLabel("Full legal name").fill("Aarav Sharma");
  await page.getByLabel("Date of birth").fill("1994-05-12");
  await page.getByLabel("Identity document number").fill("DEMO12345678");
  await page.getByLabel("Country of residence").selectOption("IN");
  await page
    .getByLabel("Identity document", { exact: false })
    .last()
    .setInputFiles(path.join(repo, "examples/kyc/synthetic-id.png"));
  await page
    .getByLabel("Selfie", { exact: false })
    .setInputFiles(path.join(repo, "examples/kyc/synthetic-selfie.png"));
  await page.getByRole("button", { name: "Submit for verification" }).click();
  await expect(
    page.getByText("Verification approved.", { exact: false }),
  ).toBeVisible();
  const data = await (await page.request.get("/api/kyc")).json();
  expect(data.status).toBe("approved");
  expect(data.submissions.length).toBeGreaterThan(0);
});

test("recommendation calculator handles a zero-interest repayment schedule", async ({
  page,
}) => {
  await customer(page);
  await page.goto("/recommendations");
  await page.getByLabel("Loan amount (INR)").fill("60000");
  await page.getByLabel("Annual interest rate (%)").fill("0");
  await page.getByLabel("Term (months)").fill("12");
  await page.getByRole("button", { name: "Calculate monthly payment" }).click();
  await expect(page.getByText(/5,000/).first()).toBeVisible();
  await expect(page.getByText(/Term Life Essential/)).toBeVisible();
});

test("new beneficiary payment requests step-up and settles after verification", async ({
  page,
}) => {
  await customer(page);
  await page.goto("/payments");
  await page
    .getByRole("button", { name: "Add recipient", exact: true })
    .click();
  await page
    .getByLabel("Recipient name", { exact: true })
    .fill("Synthetic Step Up");
  await page.getByLabel("Bank name", { exact: true }).fill("Synthetic Bank");
  await page
    .getByLabel("Account number", { exact: true })
    .fill(String(Date.now()));
  const recipientResult = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/beneficiaries") && r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Save recipient", exact: true })
    .click();
  const beneficiary = await (await recipientResult).json();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page
    .getByLabel("Recipient", { exact: true })
    .selectOption(beneficiary.id);
  await page.getByLabel("Amount (INR)", { exact: true }).fill("25000.00");
  await page
    .getByLabel("Payment description", { exact: true })
    .fill("Browser step-up transfer");
  const before = (await (await page.request.get("/api/overview")).json())
    .account.balance;
  await page
    .getByRole("button", { name: "Review transfer", exact: true })
    .click();
  const transferResult = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/transfers") && r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Confirm transfer", exact: true })
    .click();
  expect((await (await transferResult).json()).status).toBe("pending_step_up");
  expect(
    (await (await page.request.get("/api/overview")).json()).account.balance,
  ).toBe(before);
  await page
    .getByLabel("Account password (demo verification)", { exact: true })
    .fill("AegisDemo!2026");
  const verification = page.waitForResponse(
    (r) => r.url().endsWith("/step-up") && r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Verify transfer", exact: true })
    .click();
  expect((await (await verification).json()).status).toBe("posted");
  expect(
    Number(before) -
      Number(
        (await (await page.request.get("/api/overview")).json()).account
          .balance,
      ),
  ).toBe(25000);
});

test("fraud simulator holds a payment and analyst can reject with a reason", async ({
  page,
  browser,
}) => {
  await customer(page);
  await page.goto("/security");
  await page.getByLabel(/scenario/i).selectOption("impossible_travel");
  await page
    .getByRole("button", { name: /Run simulation|Simulate event/ })
    .click();
  await expect(
    page.getByText(/impossible.travel|impossible travel/i).first(),
  ).toBeVisible();
  await page.getByLabel(/scenario/i).selectOption("large_transfer");
  const responsePromise = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/simulator/events") &&
      r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: /Run simulation|Simulate event/ })
    .click();
  const data = await (await responsePromise).json();
  expect(data.transfer.status).toBe("held");
  const investigator = await browser.newContext();
  const consolePage = await investigator.newPage();
  await analyst(consolePage);
  const cases = await (
    await consolePage.request.get("/api/analyst/cases")
  ).json();
  const fraudCase = cases.find(
    (c: { transfer_id: string }) => c.transfer_id === data.transfer.id,
  );
  expect(fraudCase).toBeTruthy();
  await consolePage.goto(`/analyst/cases/${fraudCase.id}`);
  await expect(
    consolePage.getByRole("heading", { name: "Risk evidence" }),
  ).toBeVisible();
  await consolePage.getByRole("button", { name: "Reject case" }).click();
  await consolePage
    .getByLabel("Decision rationale")
    .fill("Synthetic impossible travel verified; reject this transfer.");
  await consolePage.getByRole("button", { name: "Confirm rejection" }).click();
  await expect(
    consolePage.getByText("Case rejected.", { exact: false }),
  ).toBeVisible();
  await consolePage.screenshot({
    path: path.join(repo, "test-results/analyst-case.png"),
    fullPage: true,
  });
  const transactions = await (
    await page.request.get("/api/transactions")
  ).json();
  expect(
    transactions.some(
      (t: { status: string; id: string }) => t.status === "rejected",
    ),
  ).toBeTruthy();
  await investigator.close();
});

test("mobile customer navigation remains usable without horizontal overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await customer(page);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: path.join(repo, "test-results/mobile-dashboard.png"),
    fullPage: true,
  });
  await page.goto("/documents");
  await expect(
    page.getByRole("heading", { name: "Clarity, with a source." }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBeTruthy();
});

test("assistant uses account tools, cites policy and requires payment consent", async ({
  page,
}) => {
  await customer(page);
  await page.goto("/assistant");
  const compose = page.getByLabel("Message your assistant");
  async function ask(message: string) {
    await compose.fill(message);
    const response = page.waitForResponse(
      (r) => r.url().endsWith("/api/chat") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Send message" }).click();
    const result = await response;
    expect(result.ok()).toBeTruthy();
    return result.json();
  }
  const balance = await ask("What is my available balance?");
  expect(
    balance.tools.some((t: { name: string }) => t.name === "get_balance"),
  ).toBeTruthy();
  await expect(
    page.getByText(balance.reply, { exact: true }).last(),
  ).toBeVisible();
  const policy = await ask("What does the loan policy say about prepayment?");
  expect(policy.citations.length).toBeGreaterThan(0);
  await expect(page.locator(".chat-citations").last()).toBeVisible();
  const before = (await (await page.request.get("/api/overview")).json())
    .account.balance;
  const proposal = await ask("Transfer INR 100 to Ananya Sharma");
  expect(proposal.proposal.amount).toBeTruthy();
  expect(
    (await (await page.request.get("/api/overview")).json()).account.balance,
  ).toBe(before);
  await page.getByRole("button", { name: "Review proposed payment" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Confirm proposed payment" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(page.locator(".chat-transfer-result")).toContainText(
    /held|completed|review/i,
  );
});

test("budgets persist and analyst account status changes leave audit evidence", async ({
  page,
  browser,
}) => {
  await customer(page);
  await page.goto("/dashboard");
  await page.getByRole("button", { name: "Add budget", exact: true }).click();
  await page.getByLabel("Budget category").fill("education");
  await page.getByLabel("Monthly limit (INR)").fill("3000");
  await page.getByRole("button", { name: "Save budget", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const budgets = await (await page.request.get("/api/budgets")).json();
  expect(
    budgets.find((b: { category: string }) => b.category === "education")
      .limit_amount,
  ).toBe("3000.00");
  await page.goto("/activity");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const investigation = await browser.newContext();
  const consolePage = await investigation.newPage();
  await analyst(consolePage);
  await consolePage.goto("/analyst/customers");
  await expect(consolePage.getByRole("heading", { level: 1 })).toBeVisible();
  await consolePage
    .getByRole("button", {
      name: "Freeze account for Satyam Sahu",
      exact: true,
    })
    .click();
  await consolePage
    .getByLabel("Reason for account status change")
    .fill("Browser acceptance review of synthetic security events.");
  await consolePage
    .getByRole("button", { name: "Confirm freeze", exact: true })
    .click();
  await expect(consolePage.getByRole("dialog")).not.toBeVisible();
  expect(
    (await (await page.request.get("/api/overview")).json()).account.status,
  ).toBe("frozen");
  await consolePage
    .getByRole("button", {
      name: "Unfreeze account for Satyam Sahu",
      exact: true,
    })
    .click();
  await consolePage
    .getByLabel("Reason for account status change")
    .fill("Synthetic review complete; restore test account access.");
  await consolePage
    .getByRole("button", { name: "Confirm unfreeze", exact: true })
    .click();
  await expect(consolePage.getByRole("dialog")).not.toBeVisible();
  expect(
    (await (await page.request.get("/api/overview")).json()).account.status,
  ).toBe("active");
  await consolePage.goto("/analyst/audit");
  await expect(consolePage.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(
    consolePage.getByText(/budget updated|budget_updated/i).first(),
  ).toBeVisible();
  await investigation.close();
});
