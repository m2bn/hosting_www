import { expect, test } from "@playwright/test";

async function mockCsrf(page: import("@playwright/test").Page) {
  await page.route("**/api/auth/csrf/", async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        "content-type": "application/json",
        "set-cookie": "csrftoken=test-csrf-token; Path=/; SameSite=Lax",
      },
      body: "{}",
    });
  });
}

test("logs in with cookie session and CSRF header", async ({ page }) => {
  await mockCsrf(page);

  await page.route("**/api/auth/login/", async (route) => {
    const request = route.request();
    expect(request.headers()["x-csrftoken"]).toBe("test-csrf-token");
    expect(request.postDataJSON()).toEqual({
      email: "owner@example.com",
      password: "correct-horse-battery",
    });
    await route.fulfill({
      status: 200,
      headers: { "content-type": "application/json" },
      body: "{}",
    });
  });

  await page.goto("/login");
  await page.getByLabel("Email").fill("owner@example.com");
  await page.getByLabel("Password").fill("correct-horse-battery");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
});

test("continues through two-factor challenge", async ({ page }) => {
  await mockCsrf(page);

  await page.route("**/api/auth/login/", async (route) => {
    await route.fulfill({
      status: 200,
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ requires_two_factor: true }),
    });
  });

  await page.route("**/api/auth/two-factor/", async (route) => {
    expect(route.request().headers()["x-csrftoken"]).toBe("test-csrf-token");
    expect(route.request().postDataJSON()).toEqual({
      code: "123456",
    });
    await route.fulfill({
      status: 204,
      body: "",
    });
  });

  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@example.com");
  await page.getByLabel("Password").fill("correct-horse-battery");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/two-factor$/);
  await page.getByLabel("Authenticator code").fill("123456");
  await page.getByRole("button", { name: "Verify and continue" }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
});
