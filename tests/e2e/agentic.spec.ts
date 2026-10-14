import {
  test,
  expect,
  Page,
} from "../../frontend/node_modules/@playwright/test";
import path from "node:path";

const repo = path.resolve(__dirname, "../..");
type Goal = {
  id: string;
  name: string;
  saved_amount: string;
  target_amount: string;
  status: string;
  progress_percent: number;
  planning_only: boolean;
};
type Run = {
  id: string;
  status: string;
  trace_id: string;
  tools: string[];
  decisions: string[];
  completed_at: string | null;
};
type Insight = { id: string; title: string; status: string };

async function signIn(page: Page, role: "customer" | "analyst") {
  await page.goto("/login");
  await page
    .getByRole("button", {
      name: role === "customer" ? "Customer demo" : "Analyst demo",
      exact: true,
    })
    .click();
  await expect(page).toHaveURL(
    role === "customer" ? /\/dashboard$/ : /\/analyst$/,
  );
}

async function accountBalance(page: Page): Promise<string> {
  const response = await page.request.get("/api/overview");
  expect(response.ok()).toBeTruthy();
  return (await response.json()).account.balance;
}

test("savings planning persists create, edit, completion and removal without moving ledger funds", async ({
  page,
}) => {
  await signIn(page, "customer");
  const before = await accountBalance(page);
  const name = `Browser emergency cushion ${Date.now()}`;
  await page.goto("/insights");
  await page
    .getByRole("button", { name: "Create a goal", exact: true })
    .click();
  await page.getByLabel("Goal name", { exact: true }).fill(name);
  await page.getByLabel("Target amount (INR)", { exact: true }).fill("6000.00");
  await page.getByLabel("Saved amount (INR)", { exact: true }).fill("1500.00");
  const createdResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/goals") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Save goal", exact: true }).click();
  const createdResult = await createdResponse;
  expect(createdResult.status()).toBe(201);
  const created: Goal = await createdResult.json();
  expect(created.planning_only).toBe(true);
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const progress = page.getByRole("progressbar", {
    name: `${name} savings progress`,
    exact: true,
  });
  await expect(progress).toHaveAttribute("aria-valuenow", "25");
  expect(await accountBalance(page)).toBe(before);

  await page.getByRole("button", { name: `Edit ${name}`, exact: true }).click();
  await page.getByLabel("Saved amount (INR)", { exact: true }).fill("3000.00");
  await page.getByLabel("Plan status", { exact: true }).selectOption("paused");
  const editedResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/goals/${created.id}`) &&
      response.request().method() === "PATCH",
  );
  await page.getByRole("button", { name: "Save goal", exact: true }).click();
  const editedResult = await editedResponse;
  expect(editedResult.ok()).toBeTruthy();
  expect((await editedResult.json()).status).toBe("paused");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(progress).toHaveAttribute("aria-valuenow", "50");
  const goalCard = page
    .locator(".health-goal")
    .filter({ has: page.getByRole("heading", { name, exact: true }) });
  await expect(goalCard.getByText("paused", { exact: true })).toBeVisible();
  expect(await accountBalance(page)).toBe(before);

  await page.reload();
  await expect(progress).toHaveAttribute("aria-valuenow", "50");
  await page.getByRole("button", { name: `Edit ${name}`, exact: true }).click();
  await page.getByLabel("Saved amount (INR)", { exact: true }).fill("6000.00");
  await page
    .getByLabel("Plan status", { exact: true })
    .selectOption("completed");
  await page.getByRole("button", { name: "Save goal", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(progress).toHaveAttribute("aria-valuenow", "100");
  await expect(
    goalCard.getByText("Goal reached", { exact: true }),
  ).toBeVisible();
  expect(await accountBalance(page)).toBe(before);

  await page
    .getByRole("button", { name: `Delete ${name}`, exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Remove this savings goal?" }),
  ).toBeVisible();
  const deletedResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/goals/${created.id}`) &&
      response.request().method() === "DELETE",
  );
  await page.getByRole("button", { name: "Remove goal", exact: true }).click();
  expect((await (await deletedResponse).json()).deleted).toBe(true);
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(
    page.getByRole("heading", { name, exact: true }),
  ).not.toBeVisible();
  const savedGoals: Goal[] = await (
    await page.request.get("/api/goals")
  ).json();
  expect(savedGoals.some((goal) => goal.id === created.id)).toBe(false);
  expect(await accountBalance(page)).toBe(before);
});

test("financial analysis completes with scoped tools, persisted trace and dismissible insight evidence", async ({
  page,
}) => {
  await signIn(page, "customer");
  const before = await accountBalance(page);
  await page.goto("/insights");
  const refreshButton = page.getByRole("button", {
    name: "Refresh insights",
    exact: true,
  });
  await expect(refreshButton).toBeEnabled();
  const refreshResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/insights/refresh") &&
      response.request().method() === "POST",
  );
  await refreshButton.click();
  const refreshResult = await refreshResponse;
  expect(refreshResult.status()).toBe(202);
  const queued: Run = await refreshResult.json();
  let completed: Run | undefined;
  await expect
    .poll(
      async () => {
        const response = await page.request.get("/api/agent-runs");
        expect(response.ok()).toBeTruthy();
        const runs: Run[] = await response.json();
        completed = runs.find((run) => run.id === queued.id);
        return completed?.status;
      },
      { timeout: 20000, intervals: [250, 500, 1000] },
    )
    .toBe("completed");
  expect(completed!.completed_at).toBeTruthy();
  expect(completed!.trace_id).toBeTruthy();
  expect(completed!.tools).toEqual(
    expect.arrayContaining([
      "get_balance",
      "get_spending",
      "get_budgets",
      "get_security_summary",
      "get_identity_status",
      "get_recommendations",
    ]),
  );
  expect(completed!.decisions.length).toBeGreaterThan(0);
  expect(await accountBalance(page)).toBe(before);

  await page.reload();
  const runDetails = page
    .locator(".health-run")
    .filter({ hasText: completed!.trace_id });
  await expect(runDetails).toHaveCount(1);
  await runDetails.locator("summary").click();
  await expect(runDetails.locator(".health-run-trace")).toHaveText(
    completed!.trace_id,
  );
  await expect(
    runDetails.getByText("get balance", { exact: true }),
  ).toBeVisible();
  await expect(
    runDetails.getByRole("heading", {
      name: "Recorded decisions",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    runDetails.locator(".health-run-evidence li").first(),
  ).toBeVisible();

  const response = await page.request.get("/api/insights");
  expect(response.ok()).toBeTruthy();
  const analysis: { items: Insight[] } = await response.json();
  const observation = analysis.items.find((item) => item.status === "active");
  expect(observation).toBeTruthy();
  const dismissResponse = page.waitForResponse(
    (result) =>
      result.url().endsWith(`/api/insights/${observation!.id}/dismiss`) &&
      result.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: `Dismiss ${observation!.title}`, exact: true })
    .click();
  expect((await (await dismissResponse).json()).status).toBe("dismissed");
  await expect(
    page.getByRole("button", {
      name: `Dismiss ${observation!.title}`,
      exact: true,
    }),
  ).not.toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Your financial health", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: `Dismiss ${observation!.title}`,
      exact: true,
    }),
  ).not.toBeVisible();
  expect(await accountBalance(page)).toBe(before);
  await page.screenshot({
    path: path.join(repo, "test-results/customer-financial-health.png"),
    fullPage: true,
  });
});

test("analyst policy publication requires public-sharing consent and customers can verify cited source text", async ({
  page,
  browser,
}) => {
  await signIn(page, "analyst");
  await page.goto("/analyst/integrations");
  const title = `Browser shared continuity policy ${Date.now()}`;
  const code = "PINE-AGENT-812";
  await page
    .getByRole("button", { name: "Publish a policy", exact: true })
    .click();
  const publish = page.getByRole("button", {
    name: "Publish to all customers",
    exact: true,
  });
  await expect(publish).toBeDisabled();
  await page.getByLabel("Policy title", { exact: true }).fill(title);
  await page
    .getByLabel("Policy file", { exact: true })
    .setInputFiles({
      name: "public-continuity.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(
        `The customer continuity reference code is ${code}. This approved public banking guidance requires analyst review of high-risk transfers. It does not alter automated credit eligibility, payment risk rules, or settlement permissions.`,
      ),
    });
  await page
    .getByRole("checkbox", {
      name: "I confirm this policy is approved for sharing with every AegisBank customer.",
      exact: true,
    })
    .check();
  await expect(publish).toBeEnabled();
  const publication = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/analyst/documents") &&
      response.request().method() === "POST",
  );
  await publish.click();
  const publishedResult = await publication;
  expect(publishedResult.status()).toBe(201);
  const published: { id: string; title: string; kind: string } =
    await publishedResult.json();
  expect(published.title).toBe(title);
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();

  const customerContext = await browser.newContext();
  try {
    const customerPage = await customerContext.newPage();
    await signIn(customerPage, "customer");
    await customerPage.goto("/documents");
    await customerPage.getByRole("button", { name: new RegExp(title) }).click();
    await customerPage
      .getByLabel("Ask about this document", { exact: true })
      .fill("What is the customer continuity reference code?");
    const answerResponse = customerPage.waitForResponse(
      (response) =>
        response.url().endsWith("/api/documents/query") &&
        response.request().method() === "POST",
    );
    await customerPage
      .getByRole("button", { name: "Ask document", exact: true })
      .click();
    const answerResult = await answerResponse;
    expect(answerResult.ok()).toBeTruthy();
    const answer: { citations: { document_id: string; excerpt: string }[] } =
      await answerResult.json();
    expect(
      answer.citations.some(
        (citation) =>
          citation.document_id === published.id &&
          citation.excerpt.includes(code),
      ),
    ).toBe(true);
    await expect(
      customerPage.locator("blockquote").filter({ hasText: code }),
    ).toBeVisible();
    await customerPage
      .getByRole("button", { name: "View source", exact: true })
      .click();
    const source = customerPage.getByRole("dialog", {
      name: title,
      exact: true,
    });
    await expect(source).toBeVisible();
    await expect(source).toContainText(code);
    await expect(source).toContainText("Page 1");
    await customerPage.screenshot({
      path: path.join(repo, "test-results/shared-policy-source.png"),
      fullPage: true,
    });
  } finally {
    await customerContext.close();
  }
});

test("provider readiness distinguishes runnable demo adapters and unconfigured Claude and OpenAI model access", async ({
  page,
}) => {
  await signIn(page, "analyst");
  await page.goto("/analyst/integrations");
  await expect(
    page.getByRole("heading", {
      name: "Claude & OpenAI integrations",
      exact: true,
    }),
  ).toBeVisible();
  const readinessResponse = await page.request.get("/api/analyst/integrations");
  expect(readinessResponse.ok()).toBeTruthy();
  const readiness: {
    ai_mode: string;
    providers: {
      id: string;
      integrated: boolean;
      credential_configured: boolean;
    }[];
  } = await readinessResponse.json();
  expect(readiness.ai_mode).toBe("local");
  for (const provider of ["claude", "openai"]) {
    expect(
      readiness.providers.find((item) => item.id === provider)?.integrated,
    ).toBe(true);
    expect(
      readiness.providers.find((item) => item.id === provider)
        ?.credential_configured,
    ).toBe(false);
    const probe = page.waitForResponse(
      (response) =>
        response
          .url()
          .endsWith(`/api/analyst/integrations/${provider}/check`) &&
        response.request().method() === "POST",
    );
    await page
      .getByRole("button", {
        name:
          provider === "claude"
            ? "Check Claude connection"
            : "Check OpenAI connection",
        exact: true,
      })
      .click();
    const probeResult = await probe;
    expect(probeResult.ok()).toBeTruthy();
    const payload = await probeResult.json();
    expect(payload.status).toBe("unconfigured");
    expect(payload.configured).toBe(false);
    expect(payload.scope).toBe("model_access");
    await expect(
      page.getByText(payload.message, { exact: false }).first(),
    ).toBeVisible();
  }
  expect(
    readiness.providers.find((item) => item.id === "core_banking")?.integrated,
  ).toBe(false);
  expect(
    readiness.providers.find((item) => item.id === "identity")?.integrated,
  ).toBe(false);
  await expect(
    page.getByRole("heading", {
      name: "Banking and identity adapters",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
  await page.screenshot({
    path: path.join(repo, "test-results/analyst-integrations.png"),
    fullPage: true,
  });
});

test("mobile financial health and integration workspaces remain navigable without viewport overflow", async ({
  page,
  browser,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page, "customer");
  await page
    .getByRole("button", { name: "Open navigation", exact: true })
    .click();
  await page
    .getByRole("link", { name: "Financial health", exact: true })
    .click();
  await expect(page).toHaveURL(/\/insights$/);
  await expect(
    page.getByRole("heading", { name: "Your financial health", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Your savings goals", exact: true }),
  ).toBeVisible();
  await expect
    .poll(() =>
      page
        .locator(".sidebar")
        .evaluate((element) => element.getBoundingClientRect().right),
    )
    .toBeLessThanOrEqual(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
  await page.screenshot({
    path: path.join(repo, "test-results/mobile-financial-health.png"),
    fullPage: true,
  });

  const analystContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
  });
  try {
    const consolePage = await analystContext.newPage();
    await signIn(consolePage, "analyst");
    await consolePage
      .getByRole("button", { name: "Open navigation", exact: true })
      .click();
    await consolePage
      .getByRole("link", { name: "Integrations", exact: true })
      .click();
    await expect(consolePage).toHaveURL(/\/analyst\/integrations$/);
    await expect(
      consolePage.getByRole("heading", {
        name: "Claude & OpenAI integrations",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      consolePage.getByRole("button", {
        name: "Check Claude connection",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      consolePage.getByRole("button", {
        name: "Check OpenAI connection",
        exact: true,
      }),
    ).toBeVisible();
    await expect
      .poll(() =>
        consolePage
          .locator(".sidebar")
          .evaluate((element) => element.getBoundingClientRect().right),
      )
      .toBeLessThanOrEqual(0);
    expect(
      await consolePage.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    ).toBe(true);
    await consolePage.screenshot({
      path: path.join(repo, "test-results/mobile-integrations.png"),
      fullPage: true,
    });
  } finally {
    await analystContext.close();
  }
});
