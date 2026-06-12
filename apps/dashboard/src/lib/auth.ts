import { apiRequest } from "@/lib/api";

export type LoginResult = {
  requires_two_factor?: boolean;
};

export type RegisterInput = {
  full_name: string;
  email: string;
  password: string;
};

export async function login(email: string, password: string): Promise<LoginResult> {
  return apiRequest<LoginResult>("/auth/login/", {
    method: "POST",
    body: { email, password },
    csrf: true,
  });
}

export async function register(input: RegisterInput): Promise<void> {
  await apiRequest<void>("/auth/register/", {
    method: "POST",
    body: input,
    csrf: true,
  });
}

export async function requestPasswordReset(email: string): Promise<void> {
  await apiRequest<void>("/auth/password-reset/", {
    method: "POST",
    body: { email },
    csrf: true,
  });
}

export async function resetPassword(token: string, password: string): Promise<void> {
  await apiRequest<void>("/auth/password-reset/confirm/", {
    method: "POST",
    body: { token, password },
    csrf: true,
  });
}

export async function verifyEmail(token: string): Promise<void> {
  await apiRequest<void>("/auth/verify-email/", {
    method: "POST",
    body: { token },
    csrf: true,
  });
}

export async function completeTwoFactor(code: string, recoveryCode?: string): Promise<void> {
  await apiRequest<void>("/auth/two-factor/", {
    method: "POST",
    body: { code, recovery_code: recoveryCode || undefined },
    csrf: true,
  });
}
