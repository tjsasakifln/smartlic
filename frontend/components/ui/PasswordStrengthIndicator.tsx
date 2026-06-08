"use client";

interface PasswordStrengthIndicatorProps {
  password: string;
  className?: string;
}

const RULES = [
  { test: (pw: string) => pw.length >= 8, label: "Mínimo 8 caracteres" },
  { test: (pw: string) => /[A-Z]/.test(pw), label: "Pelo menos 1 letra maiúscula" },
  { test: (pw: string) => /\d/.test(pw), label: "Pelo menos 1 número" },
  { test: (pw: string) => /[^A-Za-z0-9]/.test(pw), label: "Pelo menos 1 caractere especial" },
] as const;

/**
 * PasswordStrengthIndicator
 *
 * Shows a real-time checklist of password rules during typing.
 * - Green checkmark (svg) when rule is satisfied
 * - Gray X (svg) when rule is not yet satisfied
 * - Updates on every keystroke (onChange)
 *
 * Mobile responsive — uses text-sm on small screens, text-xs on larger.
 */
export function PasswordStrengthIndicator({
  password,
  className = "",
}: PasswordStrengthIndicatorProps) {
  if (!password) return null;

  const allPassed = RULES.every((rule) => rule.test(password));
  if (allPassed) return null;

  return (
    <ul
      className={`mt-2 space-y-1 text-sm sm:text-xs ${className}`}
      data-testid="password-strength-indicator"
    >
      {RULES.map((rule, index) => {
        const passed = rule.test(password);
        return (
          <li
            key={index}
            className={`flex items-center gap-1.5 transition-colors ${
              passed
                ? "text-green-600 dark:text-green-400"
                : "text-gray-400 dark:text-gray-500"
            }`}
            data-testid={`password-rule-${index}`}
          >
            {passed ? (
              <svg
                className="w-3.5 h-3.5 shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2.5}
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M5 13l4 4L19 7"
                />
              </svg>
            ) : (
              <svg
                className="w-3.5 h-3.5 shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            )}
            <span>{rule.label}</span>
          </li>
        );
      })}
    </ul>
  );
}
