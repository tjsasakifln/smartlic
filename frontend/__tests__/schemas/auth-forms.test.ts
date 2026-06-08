/**
 * DEBT-FE-003: Tests for auth form zod schemas
 *
 * Tests loginSchema, recuperarSenhaSchema, and redefinirSenhaSchema
 * validation rules.
 */

import {
  loginSchema,
  loginPasswordSchema,
  recuperarSenhaSchema,
  redefinirSenhaSchema,
} from "../../lib/schemas/forms";

// ============================================================================
// loginSchema
// ============================================================================

describe("loginSchema", () => {
  it("accepts valid email and password", () => {
    const result = loginSchema.safeParse({
      email: "user@example.com",
      password: "123456",
    });
    expect(result.success).toBe(true);
  });

  it("rejects empty email", () => {
    const result = loginSchema.safeParse({
      email: "",
      password: "123456",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const emailError = result.error.issues.find((i) => i.path[0] === "email");
      expect(emailError).toBeDefined();
    }
  });

  it("rejects invalid email format", () => {
    const result = loginSchema.safeParse({
      email: "not-an-email",
      password: "123456",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const emailError = result.error.issues.find((i) => i.path[0] === "email");
      expect(emailError).toBeDefined();
      expect(emailError?.message).toContain("inválido");
    }
  });

  it("accepts any password in base schema (magic link mode)", () => {
    // loginSchema is the base schema used in magic link mode — password is optional
    const result = loginSchema.safeParse({
      email: "user@example.com",
      password: "",
    });
    expect(result.success).toBe(true);
  });
});

// ============================================================================
// loginPasswordSchema (password mode — stricter)
// ============================================================================

describe("loginPasswordSchema", () => {
  it("rejects password shorter than 6 characters", () => {
    const result = loginPasswordSchema.safeParse({
      email: "user@example.com",
      password: "12345",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const pwError = result.error.issues.find((i) => i.path[0] === "password");
      expect(pwError).toBeDefined();
      expect(pwError?.message).toContain("6");
    }
  });

  it("accepts password with exactly 6 characters", () => {
    const result = loginPasswordSchema.safeParse({
      email: "user@example.com",
      password: "123456",
    });
    expect(result.success).toBe(true);
  });
});

// ============================================================================
// recuperarSenhaSchema
// ============================================================================

describe("recuperarSenhaSchema", () => {
  it("accepts valid email", () => {
    const result = recuperarSenhaSchema.safeParse({
      email: "user@example.com",
    });
    expect(result.success).toBe(true);
  });

  it("rejects empty email", () => {
    const result = recuperarSenhaSchema.safeParse({
      email: "",
    });
    expect(result.success).toBe(false);
  });

  it("rejects invalid email format", () => {
    const result = recuperarSenhaSchema.safeParse({
      email: "bad-email",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0].message).toContain("inválido");
    }
  });
});

// ============================================================================
// redefinirSenhaSchema
// ============================================================================

describe("redefinirSenhaSchema", () => {
  it("accepts matching passwords with 8+ chars, uppercase, digit, and special char", () => {
    const result = redefinirSenhaSchema.safeParse({
      password: "Newpass12!",
      confirmPassword: "Newpass12!",
    });
    expect(result.success).toBe(true);
  });

  it("rejects password shorter than 8 characters", () => {
    const result = redefinirSenhaSchema.safeParse({
      password: "short",
      confirmPassword: "short",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const pwError = result.error.issues.find((i) => i.path[0] === "password");
      expect(pwError).toBeDefined();
      expect(pwError?.message).toContain("8");
    }
  });

  it("rejects password without uppercase letter", () => {
    const result = redefinirSenhaSchema.safeParse({
      password: "nouppercase1!",
      confirmPassword: "nouppercase1!",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const pwError = result.error.issues.find((i) => i.path[0] === "password");
      expect(pwError).toBeDefined();
      expect(pwError?.message).toContain("maiúscula");
    }
  });

  it("rejects password without digit", () => {
    const result = redefinirSenhaSchema.safeParse({
      password: "NoDigitAbc!",
      confirmPassword: "NoDigitAbc!",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const pwError = result.error.issues.find((i) => i.path[0] === "password");
      expect(pwError).toBeDefined();
      expect(pwError?.message).toContain("número");
    }
  });

  it("rejects password without special character", () => {
    const result = redefinirSenhaSchema.safeParse({
      password: "NoSpecial1A",
      confirmPassword: "NoSpecial1A",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const pwError = result.error.issues.find((i) => i.path[0] === "password");
      expect(pwError).toBeDefined();
      expect(pwError?.message).toContain("especial");
    }
  });

  it("rejects mismatched passwords", () => {
    const result = redefinirSenhaSchema.safeParse({
      password: "Newpass12!",
      confirmPassword: "Diffpass1!",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const mismatchError = result.error.issues.find(
        (i) => i.path.includes("confirmPassword")
      );
      expect(mismatchError).toBeDefined();
      expect(mismatchError?.message).toContain("coincidem");
    }
  });

  it("rejects empty confirmPassword", () => {
    const result = redefinirSenhaSchema.safeParse({
      password: "Newpass12!",
      confirmPassword: "",
    });
    expect(result.success).toBe(false);
  });

  it("accepts password with exactly 8 characters meeting all rules", () => {
    const result = redefinirSenhaSchema.safeParse({
      password: "Ab12!xyz",
      confirmPassword: "Ab12!xyz",
    });
    expect(result.success).toBe(true);
  });
});
