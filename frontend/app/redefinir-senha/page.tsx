"use client";

import { useState, useEffect } from "react";
import { supabase } from "../../lib/supabase";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { redefinirSenhaSchema, type RedefinirSenhaFormData } from "../../lib/schemas/forms";
import { PasswordStrengthIndicator } from "../../components/ui/PasswordStrengthIndicator";

export default function RedefinirSenhaPage() {
  // DEBT-FE-003: react-hook-form + zod for form validation
  const {
    register,
    handleSubmit: rhfHandleSubmit,
    watch,
    formState: { errors: formErrors, isValid: formIsValid },
  } = useForm<RedefinirSenhaFormData>({
    resolver: zodResolver(redefinirSenhaSchema),
    mode: "onChange",
    reValidateMode: "onChange",
    defaultValues: { password: "", confirmPassword: "" },
  });

  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const password = watch("password");
  const [status, setStatus] = useState<"form" | "success" | "error" | "checking">("checking");
  const [error, setError] = useState<string | null>(null);
  const [hasRecoverySession, setHasRecoverySession] = useState(false);

  // AC10-AC11: Listen for Supabase RECOVERY auth event
  useEffect(() => {
    // Check if we already have a session (user clicked the recovery link)
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        setHasRecoverySession(true);
        setStatus("form");
      }
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "PASSWORD_RECOVERY" && session) {
        setHasRecoverySession(true);
        setStatus("form");
      } else if (event === "SIGNED_IN" && session && !hasRecoverySession) {
        // User may have landed here with a valid recovery token
        setHasRecoverySession(true);
        setStatus("form");
      }
    });

    // If no event fires within 3 seconds, show error
    const timeout = setTimeout(() => {
      if (!hasRecoverySession) {
        setStatus("error");
        setError(
          "Link de recuperação inválido ou expirado. Solicite um novo link."
        );
      }
    }, 3000);

    return () => {
      subscription.unsubscribe();
      clearTimeout(timeout);
    };
    // Mount-only: auth state subscription must register exactly once;
    // re-registering on every render would cause duplicate handlers.
  }, []);

  const onFormSubmit = async (data: RedefinirSenhaFormData) => {
    setError(null);
    setLoading(true);

    try {
      const { error: updateError } = await supabase.auth.updateUser({
        password: data.password,
      });

      if (updateError) throw updateError;

      // AC13: Success - redirect to /buscar
      setStatus("success");
      setTimeout(() => {
        window.location.href = "/buscar";
      }, 2000);
    } catch (err: unknown) {
      // AC14: Show error with retry option
      const errObj = err as { message?: string };
      const message = errObj?.message || "Erro ao atualizar senha";
      if (message.toLowerCase().includes("same as")) {
        setError("A nova senha não pode ser igual à senha atual.");
      } else if (message.toLowerCase().includes("weak")) {
        setError("Senha muito fraca. Use letras, números e caracteres especiais.");
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  };

  // Checking state
  if (status === "checking") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--canvas)]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--brand-blue)] mx-auto mb-4"></div>
          <p className="text-[var(--ink-secondary)]">
            Verificando link de recuperação...
          </p>
        </div>
      </div>
    );
  }

  // AC13: Success state
  if (status === "success") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--canvas)] p-4">
        <div className="w-full max-w-md p-8 bg-[var(--surface-0)] rounded-card shadow-lg text-center">
          <div className="text-6xl mb-4">&#10003;</div>
          <h2 className="text-xl font-semibold text-[var(--ink)] mb-2">
            Senha atualizada!
          </h2>
          <p className="text-[var(--ink-secondary)]">
            Sua senha foi alterada com sucesso. Redirecionando...
          </p>
        </div>
      </div>
    );
  }

  // AC14: Error state (invalid/expired link)
  if (status === "error" && !hasRecoverySession) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--canvas)] p-4">
        <div className="w-full max-w-md p-8 bg-[var(--surface-0)] rounded-card shadow-lg text-center">
          <div className="text-5xl mb-4 text-[var(--error)]">&#10007;</div>
          <h2 className="text-xl font-semibold text-[var(--ink)] mb-2">
            Link inválido
          </h2>
          <p className="text-[var(--ink-secondary)] mb-6">
            {error || "Link de recuperação inválido ou expirado."}
          </p>
          <Link
            href="/recuperar-senha"
            className="inline-block w-full py-3 bg-[var(--brand-navy)] text-white rounded-button
                       font-semibold hover:bg-[var(--brand-blue)] transition-colors text-center"
          >
            Solicitar novo link
          </Link>
          <Link
            href="/login"
            className="block mt-4 text-sm text-[var(--ink-muted)] hover:text-[var(--brand-blue)] transition-colors"
          >
            ← Voltar ao login
          </Link>
        </div>
      </div>
    );
  }

  // AC11: New password form
  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--canvas)] p-4">
      <div className="w-full max-w-md p-8 bg-[var(--surface-0)] rounded-card shadow-lg">
        <h1 className="text-2xl font-display font-bold text-center text-[var(--ink)] mb-2">
          Nova senha
        </h1>
        <p className="text-center text-[var(--ink-secondary)] mb-8">
          Escolha uma nova senha para sua conta
        </p>

        {error && (
          <div
            className="mb-4 p-3 bg-[var(--error-subtle)] border border-[var(--error)]/20 rounded-input text-sm flex items-start gap-2"
            role="alert"
          >
            <svg
              className="w-5 h-5 text-[var(--error)] flex-shrink-0 mt-0.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <span className="text-[var(--error)]">{error}</span>
          </div>
        )}

        <form onSubmit={rhfHandleSubmit(onFormSubmit)} className="space-y-4" noValidate>
          <div>
            <label
              htmlFor="new-password"
              className="block text-sm font-medium text-[var(--ink-secondary)] mb-1"
            >
              Nova senha
            </label>
            <div className="relative">
              <input
                id="new-password"
                type={showPassword ? "text" : "password"}
                {...register("password")}
                aria-invalid={!!formErrors.password}
                aria-describedby={formErrors.password ? "new-password-error" : undefined}
                className={`w-full px-4 py-3 pr-12 rounded-input border bg-[var(--surface-0)] text-[var(--ink)]
                           focus:border-[var(--brand-blue)] focus:outline-none focus:ring-2
                           focus:ring-[var(--brand-blue-subtle)] ${
                             formErrors.password ? "border-[var(--error)]" : "border-[var(--border)]"
                           }`}
                placeholder="Mínimo 8 caracteres"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-[var(--ink-muted)]
                           hover:text-[var(--ink)] transition-colors"
                aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
              >
                {showPassword ? (
                  <svg
                    role="img"
                    aria-label="Ícone"
                    className="w-5 h-5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
                    />
                  </svg>
                ) : (
                  <svg
                    role="img"
                    aria-label="Ícone"
                    className="w-5 h-5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                    />
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                    />
                  </svg>
                )}
              </button>
            </div>
            {formErrors.password && (
              <p id="new-password-error" className="mt-1 text-xs text-[var(--error)]">
                {formErrors.password.message}
              </p>
            )}
            {/* UX-307: Real-time password validation checklist */}
            <PasswordStrengthIndicator password={password} />
          </div>

          <div>
            <label
              htmlFor="confirm-password"
              className="block text-sm font-medium text-[var(--ink-secondary)] mb-1"
            >
              Confirmar nova senha
            </label>
            <input
              id="confirm-password"
              type={showPassword ? "text" : "password"}
              {...register("confirmPassword")}
              aria-invalid={!!formErrors.confirmPassword}
              aria-describedby={formErrors.confirmPassword ? "confirm-password-error" : undefined}
              className={`w-full px-4 py-3 rounded-input border bg-[var(--surface-0)] text-[var(--ink)]
                         focus:border-[var(--brand-blue)] focus:outline-none focus:ring-2
                         focus:ring-[var(--brand-blue-subtle)] ${
                           formErrors.confirmPassword ? "border-[var(--error)]" : "border-[var(--border)]"
                         }`}
              placeholder="Repita a nova senha"
            />
            {formErrors.confirmPassword && (
              <p id="confirm-password-error" className="mt-1 text-xs text-[var(--error)]">
                {formErrors.confirmPassword.message}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={loading || !formIsValid}
            className="w-full py-3 bg-[var(--brand-navy)] text-white rounded-button
                       font-semibold hover:bg-[var(--brand-blue)] transition-colors
                       disabled:opacity-50 disabled:cursor-not-allowed
                       flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <svg
                  className="animate-spin h-5 w-5"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Atualizando...
              </>
            ) : (
              "Atualizar senha"
            )}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-[var(--ink-secondary)]">
          <Link
            href="/login"
            className="text-[var(--brand-blue)] hover:underline"
          >
            ← Voltar ao login
          </Link>
        </p>
      </div>
    </div>
  );
}
