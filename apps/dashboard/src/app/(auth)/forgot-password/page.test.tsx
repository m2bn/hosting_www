import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ForgotPasswordPage from "./page";
import { requestPasswordReset } from "@/lib/auth";

vi.mock("@/lib/auth", () => ({
  requestPasswordReset: vi.fn(),
}));

describe("ForgotPasswordPage", () => {
  beforeEach(() => {
    vi.mocked(requestPasswordReset).mockReset();
  });

  it("validates email format", async () => {
    render(createElement(ForgotPasswordPage));

    await userEvent.type(screen.getByLabelText(/email/i), "invalid");
    await userEvent.click(screen.getByRole("button", { name: /send reset instructions/i }));

    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(requestPasswordReset).not.toHaveBeenCalled();
  });

  it("does not reveal whether the account exists", async () => {
    vi.mocked(requestPasswordReset).mockRejectedValue(new Error("user not found"));
    render(createElement(ForgotPasswordPage));

    await userEvent.type(screen.getByLabelText(/email/i), "missing@example.com");
    await userEvent.click(screen.getByRole("button", { name: /send reset instructions/i }));

    expect(await screen.findByText("If the address is eligible, reset instructions will be sent shortly.")).toBeInTheDocument();
    expect(screen.queryByText(/user not found/i)).not.toBeInTheDocument();
  });
});
