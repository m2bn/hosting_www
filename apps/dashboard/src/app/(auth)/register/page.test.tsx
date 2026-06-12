import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RegisterPage from "./page";
import { register } from "@/lib/auth";

vi.mock("@/lib/auth", () => ({
  register: vi.fn(),
}));

describe("RegisterPage", () => {
  beforeEach(() => {
    vi.mocked(register).mockReset();
  });

  it("validates password confirmation", async () => {
    render(createElement(RegisterPage));

    await userEvent.type(screen.getByLabelText(/full name/i), "Ada Admin");
    await userEvent.type(screen.getByLabelText(/email/i), "ada@example.com");
    await userEvent.type(screen.getByLabelText(/^password$/i), "correct-horse-battery");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "different-password");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByText("Passwords do not match.")).toBeInTheDocument();
    expect(register).not.toHaveBeenCalled();
  });

  it("submits valid registration data", async () => {
    vi.mocked(register).mockResolvedValue();
    render(createElement(RegisterPage));

    await userEvent.type(screen.getByLabelText(/full name/i), "Ada Admin");
    await userEvent.type(screen.getByLabelText(/email/i), "ada@example.com");
    await userEvent.type(screen.getByLabelText(/^password$/i), "correct-horse-battery");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "correct-horse-battery");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(register).toHaveBeenCalledWith({
      full_name: "Ada Admin",
      email: "ada@example.com",
      password: "correct-horse-battery",
    });
    expect(await screen.findByText("Registration started. Check your email to verify the account.")).toBeInTheDocument();
  });
});
