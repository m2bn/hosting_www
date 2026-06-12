import { render, screen } from "@testing-library/react";
import { waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LoginPage from "./page";
import { login } from "@/lib/auth";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/auth", () => ({
  login: vi.fn(),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    vi.mocked(login).mockReset();
    push.mockReset();
  });

  it("validates fields before submitting", async () => {
    render(createElement(LoginPage));

    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText("Email is required.")).toBeInTheDocument();
    expect(screen.getByText("Password is required.")).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it("redirects to dashboard after successful login", async () => {
    vi.mocked(login).mockResolvedValue({});
    render(createElement(LoginPage));

    await userEvent.type(screen.getByLabelText(/email/i), "owner@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "correct-horse-battery");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(login).toHaveBeenCalledWith("owner@example.com", "correct-horse-battery");
    await waitFor(() => expect(push).toHaveBeenCalledWith("/dashboard"));
  });

  it("redirects to two-factor challenge when required", async () => {
    vi.mocked(login).mockResolvedValue({ requires_two_factor: true });
    render(createElement(LoginPage));

    await userEvent.type(screen.getByLabelText(/email/i), "admin@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "correct-horse-battery");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/two-factor"));
  });

  it("shows a safe generic login error", async () => {
    vi.mocked(login).mockRejectedValue(new Error("database unavailable: internal detail"));
    render(createElement(LoginPage));

    await userEvent.type(screen.getByLabelText(/email/i), "owner@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "correct-horse-battery");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText("Unable to sign in with those credentials.")).toBeInTheDocument();
    expect(screen.queryByText(/database unavailable/i)).not.toBeInTheDocument();
  });
});
