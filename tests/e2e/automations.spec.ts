import { test, expect } from '../../frontend/node_modules/@playwright/test';

test('customer schedules and pauses a review and sees its durable run', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Customer demo', exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  const before = (await (await page.request.get('/api/overview')).json()).account.balance;
  await page.getByRole('link', { name: /Automations/ }).first().click();
  await expect(page.getByRole('heading', { name: 'Put your reviews on a schedule' })).toBeVisible();
  const card = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Security watch', exact: true }) }).first();
  await card.getByLabel('Security watch frequency').selectOption('6');
  await card.getByRole('button', { name: 'Enable schedule', exact: true }).click();
  await expect(card.getByRole('button', { name: 'Save schedule', exact: true })).toBeVisible();
  await card.getByRole('button', { name: 'Run now', exact: true }).click();
  await expect(page.getByText(/Security watch is queued/)).toBeVisible();
  await expect.poll(async () => {
    const runs = await (await page.request.get('/api/agent-runs')).json();
    return runs.some((run: { kind: string; status: string }) => run.kind === 'security_review' && run.status === 'completed');
  }).toBe(true);
  await card.getByRole('button', { name: 'Pause', exact: true }).click();
  await expect(card.getByText('paused', { exact: true })).toBeVisible();
  expect((await (await page.request.get('/api/overview')).json()).account.balance).toBe(before);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Put your reviews on a schedule' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('analyst verifies ledger and durable job health', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Analyst demo', exact: true }).click();
  await expect(page).toHaveURL(/\/analyst$/);
  await page.goto('/analyst/operations');
  await expect(page.getByRole('heading', { name: 'Ledger & workflow health' })).toBeVisible();
  await expect(page.getByText(/All account balances match/)).toBeVisible();
  const report = await page.request.get('/api/analyst/operations');
  expect(report.status()).toBe(200);
  expect((await report.json()).reconciliation.ok).toBe(true);
});
