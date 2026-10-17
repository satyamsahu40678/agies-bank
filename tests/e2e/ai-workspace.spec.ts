import { test, expect } from "../../frontend/node_modules/@playwright/test";

async function signIn(page: import("../../frontend/node_modules/@playwright/test").Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: "Customer demo", exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test("contextual AI drafts an editable goal and saves only after confirmation", async ({ page }) => {
  await signIn(page);
  const before = (await (await page.request.get("/api/overview")).json()).account.balance;
  const initialGoals = (await (await page.request.get("/api/goals")).json()).length;
  await page.getByRole("button", { name: "Ask AI about this page", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Your money, explained" })).toBeVisible();
  await dialog.getByLabel("Your AI question").fill("Create a goal for Emergency fund of INR 60000 in 12 months.");
  await dialog.getByRole("button", { name: "Ask your assistant", exact: true }).click();
  await expect(dialog.getByRole("button", { name: "Review goal draft", exact: true })).toBeVisible();
  expect((await (await page.request.get("/api/goals")).json()).length).toBe(initialGoals);
  await dialog.getByRole("button", { name: "Review goal draft", exact: true }).click();
  await dialog.getByLabel("AI goal name", { exact: true }).fill("AI browser emergency plan");
  await dialog.getByLabel("AI goal target amount", { exact: true }).fill("72000");
  await dialog.getByRole("button", { name: "Save this goal", exact: true }).click();
  await expect(dialog.getByRole("link", { name: "View saved goals", exact: true })).toBeVisible();
  const goals = await (await page.request.get("/api/goals")).json();
  expect(goals.length).toBe(initialGoals + 1);
  expect(goals.find((goal: { name: string }) => goal.name === "AI browser emergency plan").target_amount).toBe("72000.00");
  expect((await (await page.request.get("/api/overview")).json()).account.balance).toBe(before);
  await dialog.getByRole("button", { name: "Close dialog", exact: true }).click();
  await page.goto("/insights");
  await expect(page.getByRole("heading", { name: "AI browser emergency plan", exact: true })).toBeVisible();
});

test("analysis explains estimates with AI and fits a mobile viewport", async ({ page }) => {
  await signIn(page);
  await page.goto("/analysis");
  await expect(page.getByRole("heading", { name: "See what your money is telling you", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "In 90 days", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Explain forecast", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Cash-flow outlook", exact: true })).toBeVisible();
  await expect(dialog.getByText(/planning shortfall, not an available overdraft/)).toBeVisible();
  await expect(dialog.getByText(/orchestrator|trace_id|ledger:read|scoped tool/)).toHaveCount(0);
  await dialog.getByRole("button", { name: "Close dialog", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Possible recurring expenses", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(page.getByRole("button", { name: "Ask AI about this page", exact: true })).toBeInViewport();
});

test("banking library links primary sources and AI returns an attributed citation", async ({ page }) => {
  await signIn(page);
  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "Learn from trusted banking sources", exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: "Search banking guides", exact: true }).fill("deposit insurance");
  const guide = page.locator("section").filter({ has: page.getByRole("heading", { name: "How deposit insurance works", exact: true }) }).first();
  await expect(guide.getByRole("link", { name: "Official source", exact: true })).toHaveAttribute("href", "https://www.dicgc.org.in/FAQs");
  await guide.getByRole("button", { name: "Read guide", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Deposit insurance in India", exact: true })).toBeVisible();
  await guide.getByRole("button", { name: "Explain with AI", exact: true }).click();
  const dialog = page.getByRole("dialog");
  const citation = dialog.locator("details").first();
  await expect(citation.locator("summary")).toContainText("How deposit insurance works");
  await citation.locator("summary").click();
  await expect(citation.getByRole("link")).toHaveAttribute("href", "https://www.dicgc.org.in/FAQs");
  await expect(citation.getByText(/reviewed 2026-10-17/)).toBeVisible();
});
