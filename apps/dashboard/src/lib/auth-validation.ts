export type FieldErrors = Record<string, string>;

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const TOTP_PATTERN = /^\d{6}$/;

export function validateEmail(email: string): string {
  if (!email.trim()) {
    return "Email is required.";
  }
  if (!EMAIL_PATTERN.test(email)) {
    return "Enter a valid email address.";
  }
  return "";
}

export function validatePassword(password: string): string {
  if (!password) {
    return "Password is required.";
  }
  if (password.length < 12) {
    return "Use at least 12 characters.";
  }
  return "";
}

export function validateRequired(value: string, label: string): string {
  return value.trim() ? "" : `${label} is required.`;
}

export function validatePasswordConfirmation(password: string, confirmation: string): string {
  if (!confirmation) {
    return "Confirm the password.";
  }
  return password === confirmation ? "" : "Passwords do not match.";
}

export function validateTwoFactorCode(code: string, recoveryCode: string): string {
  if (recoveryCode.trim()) {
    return "";
  }
  if (!code.trim()) {
    return "Enter a 6-digit code or a recovery code.";
  }
  return TOTP_PATTERN.test(code) ? "" : "Enter a 6-digit code.";
}

export function hasErrors(errors: FieldErrors): boolean {
  return Object.values(errors).some(Boolean);
}
