import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TwoFactorPage from "./page";
import { completeTwoFactor } from "@/lib/auth";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/auth", () => ({
  completeTwoFactor: vi.fn(),
}));

describe("TwoFactorPage", () => {
  beforeEach(() => {
    vi.mocked(completeTwoFactor).mockReset();
    push.mockReset();
  });

  it("requires a six-digit code or recovery code", async () => {
    render(createElement(TwoFactorPage));

    await userEvent.type(screen.getByLabelText(/authenticator code/i), "123");
    await userEvent.click(screen.getByRole("button", { name: /verify and continue/i }));

    expect(await screen.findByText("Enter a 6-digit code.")).toBeInTheDocument();
    expect(completeTwoFactor).not.toHaveBeenCalled();
  });

  it("submits a valid TOTP code and redirects", async () => {
    vi.mocked(completeTwoFactor).mockResolvedValue();
    render(createElement(TwoFactorPage));

    await userEvent.type(screen.getByLabelText(/authenticator code/i), "123456");
    await userEvent.click(screen.getByRole("button", { name: /verify and continue/i }));

    expect(completeTwoFactor).toHaveBeenCalledWith("123456", "");
    expect(push).toHaveBeenCalledWith("/dashboard");
  });
});
