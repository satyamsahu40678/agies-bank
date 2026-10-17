import { test, expect } from "../../frontend/node_modules/@playwright/test";

test("assistant renders safe Markdown in history and new replies", async ({ page }) => {
  const markdown = [
    "## Account summary",
    "**Available** funds and *careful* planning.",
    "- Review spending\n- Keep an emergency fund",
    "> Check the source before acting.",
    "| Item | Status |\n| --- | --- |\n| Balance | Reviewed |",
    '```javascript\nconsole.log("safe");\n```',
    "[Documentation](https://example.com/docs)",
    "[Unsafe link](javascript:alert(1))",
    '<img src="https://example.com/tracker" onerror="window.markdownExecuted=true">',
    '<script>window.markdownExecuted=true</script>',
  ].join("\n\n");
  const messages = [{
    id: "markdown-history", role: "assistant", content: markdown,
    agent: "orchestrator", created_at: "2026-10-17T12:00:00Z",
  }];
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    let body: unknown = [];
    if (path === "/api/auth/me") {
      body = { user: { id: "markdown-customer", name: "Demo Customer", email: "customer@aegis.demo", role: "customer" }, csrf_token: "synthetic-markdown-csrf" };
    } else if (path === "/api/health") {
      body = { status: "ok", ai_mode: "gemini", demo_enabled: true };
    } else if (path === "/api/chat" && request.method() === "POST") {
      const reply = "### Follow-up\n\nYour **Markdown** reply is ready.";
      messages.push(
        { id: "markdown-user", role: "user", content: request.postDataJSON().message, agent: "orchestrator", created_at: "2026-10-17T12:01:00Z" },
        { id: "markdown-reply", role: "assistant", content: reply, agent: "orchestrator", created_at: "2026-10-17T12:01:01Z" },
      );
      body = { reply, agent: "orchestrator", tools: [{ name: "get_balance", summary: "A scoped tool result" }], citations: [], trace_id: "synthetic-markdown-trace", ai_mode: "gemini" };
    } else if (path === "/api/chat") {
      body = messages;
    }
    await route.fulfill({ json: body });
  });

  await page.goto("/assistant");
  const rendered = page.locator(".chat-markdown").first();
  await expect(rendered.getByRole("heading", { name: "Account summary" })).toBeVisible();
  await expect(rendered.locator("strong")).toHaveText("Available");
  await expect(rendered.locator("li")).toHaveCount(2);
  await expect(rendered.getByRole("cell", { name: "Balance", exact: true })).toBeVisible();
  await expect(rendered.locator("pre code")).toContainText('console.log("safe");');
  const link = rendered.getByRole("link", { name: "Documentation", exact: true });
  await expect(link).toHaveAttribute("href", "https://example.com/docs");
  await expect(link).toHaveAttribute("rel", "noopener noreferrer");
  await expect(rendered.locator("a").filter({ hasText: "Unsafe link" })).not.toHaveAttribute("href", /^javascript:/i);
  await expect(rendered.locator("script, img, iframe")).toHaveCount(0);
  expect(await page.evaluate(() => "markdownExecuted" in window)).toBe(false);

  await page.getByPlaceholder("Ask about your money, documents, or next move…").fill("**Keep this literal**");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Follow-up", exact: true })).toBeVisible();
  await expect(page.locator(".user-message .message-content").last()).toHaveText("**Keep this literal**");
  await expect(page.locator(".user-message strong")).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Follow-up", exact: true })).toBeVisible();
  await expect(page.getByText("Aegis assistant", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/model-assisted routing|governed tool|orchestrator|synthetic-markdown-trace/i)).toHaveCount(0);
  await expect(page.locator(".message-tools, .execution-tools, .trace-id, .assistant-disclosure")).toHaveCount(0);
  await page.setViewportSize({ width: 1280, height: 420 });
  const sidebar = page.locator("aside.sidebar");
  expect(await sidebar.evaluate(element => element.scrollHeight > element.clientHeight)).toBe(true);
  await sidebar.evaluate(element => { element.scrollTop = element.scrollHeight; });
  await expect(sidebar.getByRole("button", { name: "Sign out", exact: true })).toBeInViewport();
});
