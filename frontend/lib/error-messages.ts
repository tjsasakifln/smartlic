// ── UX-310: Error Categories (AC1) ──────────────────────────────────────
export type ErrorCategory = 'network' | 'server' | 'permission' | 'data' | 'timeout' | 'unknown';

export interface StructuredError {
  /** Short title describing the problem */
  title: string;
  /** What happened + why */
  description: string;
  /** What the user can do about it */
  action: string;
}

/**
 * UX-310 AC2: Mapeamento de códigos HTTP para categorias de erro.
 * 401/403 → permission, 429/5xx → server, 408/504 → timeout, 400/404/422 → data, fetch/network → network
 */
export function httpStatusToCategory(status: number | null | undefined): ErrorCategory {
  if (status == null) return 'unknown';
  if (status === 0) return 'network';
  if (status === 401 || status === 403) return 'permission';
  if (status === 408 || status === 504) return 'timeout';
  if (status === 429 || (status >= 500 && status < 600)) return 'server';
  if (status >= 400 && status < 500) return 'data';
  return 'unknown';
}

// ── UX-310 AC3: Structured error messages per category ────────────────
const STRUCTURED_ERRORS: Record<ErrorCategory, StructuredError> = {
  network: {
    title: 'Falha de conexão',
    description: 'Não foi possível conectar ao servidor. Sua conexão de internet pode estar instável ou o servidor pode estar temporariamente fora do ar.',
    action: 'Verifique sua conexão de internet e tente novamente.',
  },
  server: {
    title: 'Erro no servidor',
    description: 'O servidor encontrou um problema ao processar sua requisição. Nossa equipe já foi notificada automaticamente.',
    action: 'Aguarde alguns minutos e tente novamente. Se o problema persistir, entre em contato com o suporte.',
  },
  permission: {
    title: 'Acesso não permitido',
    description: 'Você não tem permissão para acessar este recurso. Sua sessão pode ter expirado ou sua conta pode não ter acesso a esta funcionalidade.',
    action: 'Tente fazer login novamente. Se o problema continuar, verifique se sua conta está ativa ou contate o suporte.',
  },
  data: {
    title: 'Problema ao carregar dados',
    description: 'Não foi possível carregar os dados solicitados. Isso pode acontecer quando há muitos resultados ou os filtros são muito abrangentes.',
    action: 'Tente refinar sua busca com filtros mais específicos ou reduza o período de análise.',
  },
  timeout: {
    title: 'Tempo limite excedido',
    description: 'A operação demorou mais que o esperado e excedeu o tempo limite. Isso pode acontecer com buscas muito abrangentes.',
    action: 'Tente novamente com um escopo menor, reduzindo o número de estados ou o período de datas.',
  },
  unknown: {
    title: 'Algo deu errado',
    description: 'Ocorreu um erro inesperado. Nossa equipe já foi notificada.',
    action: 'Tente novamente em alguns instantes. Se o problema persistir, entre em contato com o suporte.',
  },
};

/**
 * UX-310 AC4: Retorna erro categorizado com título, descrição e ação.
 * Aceita categoria opcional para override manual.
 * NUNCA retorna mensagem genérica — sempre tem ação sugerida.
 */
export function getStructuredError(error: unknown, category?: ErrorCategory): StructuredError {
  if (category && category !== 'unknown') {
    return STRUCTURED_ERRORS[category];
  }

  // Infer category from HTTP status
  const httpStatus = extractHttpStatus(error);
  const inferredCategory = httpStatusToCategory(httpStatus);
  if (inferredCategory !== 'unknown') {
    return STRUCTURED_ERRORS[inferredCategory];
  }

  const msg = extractRawMessage(error).toLowerCase();

  // Detect network errors by message content
  const networkPatterns = ['fetch failed', 'failed to fetch', 'networkerror', 'network error', 'load failed', 'econnrefused', 'err_connection_refused', 'conexão', 'conexao'];
  if (networkPatterns.some(p => msg.includes(p))) {
    return STRUCTURED_ERRORS.network;
  }

  // Detect timeout by message content
  const timeoutPatterns = ['timeout', 'demorou', 'tempo limite'];
  if (timeoutPatterns.some(p => msg.includes(p))) {
    return STRUCTURED_ERRORS.timeout;
  }

  // Detect permission by message content
  const permissionPatterns = ['401', '403', 'session expired', 'sessão expirada', 'access denied', 'acesso negado', 'unauthorized', 'não autorizado'];
  if (permissionPatterns.some(p => msg.includes(p))) {
    return STRUCTURED_ERRORS.permission;
  }

  // Detect server by error code patterns
  const serverPatterns = ['502', '503', '500', '429', 'internal server error', 'service unavailable', 'bad gateway', 'backend indisponível', 'quota excedida'];
  if (serverPatterns.some(p => msg.includes(p))) {
    return STRUCTURED_ERRORS.server;
  }

  // Detect data errors
  const dataPatterns = ['400', '404', '422', 'not found', 'validation error', 'invalid'];
  if (dataPatterns.some(p => msg.includes(p))) {
    return STRUCTURED_ERRORS.data;
  }

  return STRUCTURED_ERRORS.unknown;
}

function extractHttpStatus(error: unknown): number | null {
  if (error === null || error === undefined) return null;
  if (typeof error !== 'object') return null;
  if ('response' in error) {
    const resp = (error as Record<string, unknown>).response;
    if (resp && typeof resp === 'object' && 'status' in resp) {
      return Number((resp as Record<string, unknown>).status) || null;
    }
  }
  if ('status' in error) {
    return Number((error as Record<string, unknown>).status) || null;
  }
  return null;
}

function extractRawMessage(error: unknown): string {
  if (typeof error === 'string') return error;
  if (error instanceof Error) return error.message;
  if (error !== null && typeof error === 'object') {
    if ('response' in error && error.response !== null && typeof error.response === 'object' && 'data' in (error.response as Record<string, unknown>)) {
      const data = (error.response as Record<string, unknown>).data;
      if (data && typeof data === 'object') {
        if ('detail' in (data as Record<string, unknown>)) {
          const detail = (data as Record<string, unknown>).detail;
          if (typeof detail === 'string') return detail;
          if (detail && typeof detail === 'object' && 'message' in (detail as Record<string, unknown>)) {
            return String((detail as Record<string, unknown>).message);
          }
        }
        if ('message' in (data as Record<string, unknown>)) {
          return String((data as Record<string, unknown>).message);
        }
      }
    }
    if ('message' in error) {
      return String((error as Record<string, unknown>).message);
    }
  }
  try { return String(error); } catch { return ''; }
}

// ── Backward-compatible string mapping ────────────────────────────────

const ERROR_MAP: Record<string, string> = {
  // Network errors
  "fetch failed": "Erro de conexão. Verifique sua internet.",
  "Failed to fetch": "Erro de conexão. Verifique sua internet.",
  "NetworkError": "Erro de conexão. Verifique sua internet.",
  "network error": "Erro de conexão. Verifique sua internet.",
  "Load failed": "Erro de conexão. Verifique sua internet.",

  // SSL errors
  "ERR_CERT_COMMON_NAME_INVALID": "Problema de segurança no servidor. Tente novamente em instantes.",
  "ERR_CERT": "Problema de segurança no servidor. Tente novamente em instantes.",

  // HTTP status errors (TD-006 AC2: all 10 codes mapped)
  "400": "Requisição inválida. Verifique os dados e tente novamente.",
  "503": "Serviço temporariamente indisponível. Tente em alguns minutos.",
  "502": "O servidor está temporariamente indisponível. Tente novamente em instantes.",
  "504": "A busca está demorando. Tente novamente em alguns minutos.",
  "500": "Erro interno do servidor. Tente novamente.",
  "429": "Muitas requisições. Aguarde um momento e tente novamente.",
  "401": "Sessão expirada. Faça login novamente.",
  "403": "Acesso negado. Verifique suas permissões.",
  "404": "Recurso não encontrado.",
  "408": "A requisição demorou muito. Tente novamente.",

  // JSON parse errors (backend returned HTML instead of JSON)
  "Unexpected token": "Erro temporário de comunicação. Tente novamente.",
  "is not valid JSON": "Erro temporário de comunicação. Tente novamente.",
  "Resposta inesperada": "Erro temporário de comunicação. Tente novamente.",

  // CRIT-017: Infrastructure errors that should never leak (defense-in-depth)
  "Application not found": "Nossos servidores estão sendo atualizados. Tente novamente em alguns instantes.",
  "Bad Gateway": "O servidor está temporariamente indisponível. Tente novamente em instantes.",
  "Service Unavailable": "Serviço temporariamente indisponível. Tente em alguns minutos.",
  "Gateway Timeout": "A requisição demorou muito. Tente novamente.",
  "Nossos servidores estão sendo atualizados": "keep_original",

  // UX-354 AC4-AC5 + UX-357 AC1-AC4: Server restart messages (unified to max 2 variants)
  "Server restart": "O servidor reiniciou. Recomendamos tentar novamente.",
  "retry recommended": "O servidor reiniciou. Recomendamos tentar novamente.",
  "reiniciou": "O servidor reiniciou. Recomendamos tentar novamente.",
  "Connection reset": "A conexão foi interrompida. Tente novamente.",
  "connection refused": "Servidor temporariamente indisponível. Tente novamente em instantes.",
  "Internal server error": "Erro interno do servidor. Tente novamente.",
  "Pipeline failed": "A análise não pôde ser concluída. Tente novamente.",
  "All sources failed": "Nenhuma fonte de dados respondeu. Tente novamente em alguns minutos.",
  "No results found": "Nenhum resultado encontrado para os filtros selecionados.",

  // Backend specific — CRIT-082: simplified messages without ambiguous "análise concluída" hint
  "Backend indisponível": "Não foi possível conectar ao servidor. Tente novamente em alguns minutos.",
  "Erro ao buscar licitações": "Não foi possível conectar ao servidor. Tente novamente em alguns minutos.",
  "Quota excedida": "Suas análises do mês acabaram. Faça upgrade para continuar.",

  // Timeout / PNCP specific (from backend detail messages)
  "excedeu o tempo limite": "A busca está demorando. Tente novamente em alguns minutos.",
    "PNCP está temporariamente": "Nossas fontes estão temporariamente indisponíveis. Tente novamente em instantes.",
  "tempo limite de": "A busca está demorando. Tente novamente em alguns minutos.",

  // UX FIX: Plan limit errors (date range)
  "período da análise não pode exceder": "keep_original", // Let the full message through
  "excede o limite de": "keep_original", // Let the full message through
  "Período de": "keep_original", // Let the full message through

  // CRIT-005 AC19: Response state mappings
  "empty_failure": "As fontes de dados estão temporariamente indisponíveis. Tente novamente em alguns minutos.",
  "degraded": "Alguns resultados podem estar incompletos. Fontes parcialmente disponíveis.",
  "sources_unavailable": "Não foi possível acessar as fontes de dados. Tente novamente em instantes.",
};

/**
 * Converts a technical error message to a user-friendly Portuguese message.
 * Strips URLs, stack traces, and technical jargon.
 *
 * HOTFIX 2026-02-10: Enhanced to properly extract error messages from API responses,
 * fixing "[object Object]" display bug that was showing to paying users.
 */
export function getUserFriendlyError(error: unknown): string {
  // HOTFIX: Handle API error responses (Axios/fetch error objects)
  // This fixes the "[object Object]" bug
  let message: string;

  if (typeof error === 'string') {
    message = error;
  } else if (error instanceof Error) {
    message = error.message;
  } else if (
    error !== null &&
    typeof error === 'object' &&
    'response' in error &&
    error.response !== null &&
    typeof error.response === 'object' &&
    'data' in error.response
  ) {
    // Axios error with structured response
    const data = (error.response as Record<string, unknown>).data;

    // Try to extract message from various formats
    if (
      data !== null && typeof data === 'object' &&
      'detail' in data &&
      data.detail !== null && typeof data.detail === 'object' &&
      'message' in data.detail &&
      typeof (data.detail as Record<string, unknown>).message === 'string'
    ) {
      // FastAPI HTTPException with structured detail
      message = (data.detail as Record<string, string>).message;
    } else if (
      data !== null && typeof data === 'object' &&
      'detail' in data &&
      typeof (data as Record<string, unknown>).detail === 'string'
    ) {
      // FastAPI HTTPException with string detail
      message = (data as Record<string, string>).detail;
    } else if (
      data !== null && typeof data === 'object' &&
      'message' in data &&
      typeof (data as Record<string, unknown>).message === 'string'
    ) {
      // Simple message field
      message = (data as Record<string, string>).message;
    } else if (typeof data === 'string') {
      // Entire data is a string
      message = data;
    } else {
      // Fallback: couldn't extract message from object
      console.error('Could not extract error message from:', data);
      message = "Não foi possível processar sua análise. Tente novamente em instantes.";
    }
  } else if (
    error !== null && typeof error === 'object' &&
    'request' in error &&
    !('response' in error)
  ) {
    // Network error (request sent but no response)
    message = "Erro de conexão. Verifique sua internet.";
  } else if (
    error !== null && typeof error === 'object' &&
    'message' in error &&
    typeof (error as Record<string, unknown>).message === 'string'
  ) {
    // Error object with message
    message = (error as Record<string, string>).message;
  } else {
    // Unknown error format
    console.error('Unknown error format:', error);
    message = "Erro desconhecido. Por favor, tente novamente.";
  }

  // Now apply user-friendly mappings to the extracted message
  // Check exact matches first
  if (ERROR_MAP[message]) {
    const mapped = ERROR_MAP[message];
    return mapped === "keep_original" ? message : mapped;
  }

  // Check partial matches
  for (const [key, value] of Object.entries(ERROR_MAP)) {
    if (message.toLowerCase().includes(key.toLowerCase())) {
      // UX FIX: "keep_original" means pass the full message through
      if (value === "keep_original") {
        return message;
      }
      return value;
    }
  }

  // Strip URLs from the message
  const stripped = message.replace(/https?:\/\/[^\s]+/g, '').trim();

  // Check if message has stack traces or technical jargon (TypeError, ReferenceError, etc.)
  const hasTechnicalJargon =
    stripped.includes('Error:') ||
    stripped.includes('TypeError') ||
    stripped.includes('ReferenceError') ||
    stripped.includes('at ') || // stack trace
    stripped.includes('Line ') || // stack trace
    stripped.match(/\w+Error:/); // any XxxError:

  // UX FIX: Only treat as technical if it contains actual technical jargon
  // Allow longer user-friendly messages (up to 200 chars) to pass through
  if (hasTechnicalJargon) {
    return "Algo deu errado. Tente novamente em instantes.";
  }

  // If message is user-friendly (even if long), keep it
  // Example: "O período da análise não pode exceder 7 dias..." (>100 chars but clear)
  if (stripped.length <= 200) {
    return stripped;
  }

  // Message is too long and possibly not user-friendly
  return "Algo deu errado. Tente novamente em instantes.";
}

/**
 * UX-310: Retorna erro estruturado com título, descrição e ação.
 * Aceita Error, fetch Response, string, ou categoria explícita.
 * NUNCA retorna mensagem genérica — sempre tem ação sugerida.
 */
export const getErrorMessage = getStructuredError;

/**
 * Alias for getUserFriendlyError (string return).
 * Mantido para compatibilidade — prefira getErrorMessage() para erros estruturados.
 */
export const getErrorMessageLegacy = getUserFriendlyError;

/** Default fallback message for unknown errors (TD-006 AC8). */
export const DEFAULT_ERROR_MESSAGE = "Ocorreu um erro inesperado. Tente novamente.";


/**
 * CRIT-008 AC4: HTTP status codes that indicate transient (recoverable) errors.
 * These trigger auto-retry with countdown in the frontend.
 */
/** Internal status code for client-side timeout (not a real HTTP code — never expose to users). */
export const CLIENT_TIMEOUT_STATUS = 524;

export const TRANSIENT_HTTP_CODES = new Set([502, 503, 504, CLIENT_TIMEOUT_STATUS]);

/**
 * GTM-UX-003 AC4-AC7: Contextual retry messages by error type.
 * NEVER says "servidor reiniciando" — uses specific messages per error category.
 */
export function getRetryMessage(httpStatus: number | null, rawMessage?: string): string {
  const msg = (rawMessage || '').toLowerCase();

  // Timeout errors (no HTTP codes or technical details exposed)
  if (httpStatus === 504 || httpStatus === CLIENT_TIMEOUT_STATUS || msg.includes('timeout') || msg.includes('demorou') || msg.includes('tempo limite')) {
    return 'A busca está demorando. Estamos tentando novamente automaticamente.';
  }

  // Service unavailable
  if (httpStatus === 502 || httpStatus === 503) {
    return 'O servidor está se atualizando.';
  }

  // Network errors
  if (
    msg.includes('fetch failed') ||
    msg.includes('failed to fetch') ||
    msg.includes('networkerror') ||
    msg.includes('network error') ||
    msg.includes('load failed') ||
    msg.includes('econnrefused') ||
    msg.includes('err_connection_refused') ||
    msg.includes('conexão') ||
    msg.includes('conexao')
  ) {
    return 'Verificando conexão. Tentando novamente automaticamente.';
  }

  // Generic transient
  return 'Estamos tentando novamente automaticamente.';
}

/**
 * CRIT-008 AC4: Classify whether an error is transient (server restart, network blip)
 * vs permanent (bad request, auth failure). Only transient errors get auto-retry.
 */
export function isTransientError(httpStatus: number | null, message?: string): boolean {
  if (httpStatus && TRANSIENT_HTTP_CODES.has(httpStatus)) return true;
  if (!message) return false;
  const msg = message.toLowerCase();
  return (
    msg.includes('fetch failed') ||
    msg.includes('failed to fetch') ||
    msg.includes('networkerror') ||
    msg.includes('network error') ||
    msg.includes('load failed') ||
    msg.includes('econnrefused') ||
    msg.includes('err_connection_refused')
  );
}

/**
 * GTM-PROXY-001 AC4-AC8: Centralized Supabase Auth error translations.
 * Maps English auth errors from Supabase to user-friendly Portuguese messages.
 * Used by login, signup, and any other auth-related flows.
 */
export const AUTH_ERROR_MAP: Record<string, string> = {
  // AC4: Invalid credentials
  "Invalid login credentials": "Email ou senha incorretos",
  // AC5: Duplicate registration
  "User already registered": "Este email já está cadastrado",
  // AC6: Unconfirmed email
  "Email not confirmed": "Confirme seu email antes de fazer login",
  // AC7: Password policy
  "Password should be at least 6 characters": "A senha deve ter pelo menos 6 caracteres",
  // Additional common Supabase auth errors
  "Error sending magic link email": "Este email ainda não está cadastrado. Crie sua conta para começar.",
  "For security purposes, you can only request this after": "Por segurança, aguarde alguns segundos antes de tentar novamente.",
  "Email rate limit exceeded": "Muitas tentativas. Aguarde alguns minutos.",
  "User not found": "Usuário não encontrado. Verifique o email ou crie uma conta.",
  "Signups not allowed for this instance": "Cadastros não permitidos no momento.",
  "Unable to validate email address: invalid format": "Formato de email inválido.",
  // Network errors (shared with ERROR_MAP)
  "fetch failed": "Erro de conexão. Verifique sua internet.",
  "Failed to fetch": "Erro de conexão. Verifique sua internet.",
  "NetworkError": "Erro de conexão. Verifique sua internet.",
  "network error": "Erro de conexão. Verifique sua internet.",
};

/**
 * GTM-PROXY-001 AC8: Translate Supabase auth error to Portuguese.
 * Checks exact match first, then partial match.
 * Returns original message if no translation found.
 */
export function translateAuthError(message: string): string {
  // Exact match
  if (AUTH_ERROR_MAP[message]) {
    return AUTH_ERROR_MAP[message];
  }
  // Partial match
  for (const [key, value] of Object.entries(AUTH_ERROR_MAP)) {
    if (message.toLowerCase().includes(key.toLowerCase())) {
      return value;
    }
  }
  return message;
}

/**
 * CRIT-009 AC11: Maps backend SearchErrorCode values to user-friendly Portuguese messages.
 * These are more specific than getUserFriendlyError() and take precedence when error_code is present.
 */
export const ERROR_CODE_MESSAGES: Record<string, string> = {
  BACKEND_UNAVAILABLE: "Estamos voltando em instantes. Tente novamente em alguns segundos.",
  SOURCE_UNAVAILABLE: "As fontes de dados estão temporariamente em manutenção. Tente novamente em breve.",
  ALL_SOURCES_FAILED: "Nenhuma fonte respondeu a tempo. Tente novamente em 2-3 minutos.",
  TIMEOUT: "A análise demorou mais que o esperado. Tente com menos estados ou um período menor.",
  CLIENT_TIMEOUT: "A análise demorou mais que o esperado. Tente com menos estados ou um período menor.",
  RATE_LIMIT: "Muitas análises em sequência. Aguarde 1 minuto e tente novamente.",
  QUOTA_EXCEEDED: "Suas análises deste mês foram utilizadas. Faça upgrade para continuar.",
  VALIDATION_ERROR: "Verifique os filtros selecionados e tente novamente.",
  INTERNAL_ERROR: "Algo deu errado do nosso lado. Nossa equipe já foi avisada.",
};

// =============================================================================
// STAB-006 AC2: Humanized error messages with action suggestions
// =============================================================================

export interface HumanizedError {
  /** User-friendly message (blue/yellow tone, never red) */
  message: string;
  /** Suggested action label for primary button */
  actionLabel: string;
  /** Secondary action label (optional) */
  secondaryActionLabel?: string;
  /** Color tone: 'blue' for informational, 'yellow' for warning */
  tone: "blue" | "yellow";
  /** Whether to suggest scope reduction */
  suggestReduceScope: boolean;
}

/**
 * STAB-006 AC2: Get humanized error with action suggestions.
 * Uses blue/yellow colors ONLY (never red) per UX guidelines.
 */
export function getHumanizedError(
  httpStatus: number | null,
  rawMessage: string | null,
  partialCount?: number,
  totalCount?: number
): HumanizedError {
  const msg = (rawMessage || "").toLowerCase();

  // Timeout errors (504, client-side timeout, etc.)
  if (httpStatus === 504 || httpStatus === CLIENT_TIMEOUT_STATUS || msg.includes("timeout") || msg.includes("demorou")) {
    return {
      message: "A busca está demorando. Estamos tentando novamente automaticamente.",
      actionLabel: "Tentar novamente",
      secondaryActionLabel: "Reduzir escopo",
      tone: "blue",
      suggestReduceScope: true,
    };
  }

  // Partial failure (some UFs responded)
  if (partialCount != null && totalCount != null && partialCount > 0 && partialCount < totalCount) {
    return {
      message: `Resultados parciais: ${partialCount} de ${totalCount} estados responderam`,
      actionLabel: "Tentar novamente",
      tone: "blue",
      suggestReduceScope: false,
    };
  }

  // Backend down (502/503)
  if (httpStatus === 502 || httpStatus === 503) {
    return {
      message: "Nossos servidores estão se atualizando.",
      actionLabel: "Tentar novamente",
      tone: "blue",
      suggestReduceScope: false,
    };
  }

  // Rate limit
  if (httpStatus === 429) {
    return {
      message: "Muitas consultas simultâneas. Aguarde alguns segundos.",
      actionLabel: "Tentar novamente",
      tone: "yellow",
      suggestReduceScope: false,
    };
  }

  // Network errors
  if (
    msg.includes("fetch failed") ||
    msg.includes("failed to fetch") ||
    msg.includes("networkerror") ||
    msg.includes("network error")
  ) {
    return {
      message: "Erro de conexão. Verifique sua internet e tente novamente.",
      actionLabel: "Tentar novamente",
      tone: "yellow",
      suggestReduceScope: false,
    };
  }

  // Default
  return {
    message: "Algo inesperado aconteceu. Tente novamente.",
    actionLabel: "Tentar novamente",
    tone: "blue",
    suggestReduceScope: false,
  };
}

/**
 * CRIT-009 AC11: Get user-friendly message from error_code, with fallback to generic mapping.
 */
export function getMessageFromErrorCode(errorCode: string | null | undefined): string | null {
  if (!errorCode) return null;
  return ERROR_CODE_MESSAGES[errorCode] || null;
}
