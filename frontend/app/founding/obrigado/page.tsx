import { permanentRedirect } from 'next/navigation';

/**
 * 301 redirect to the canonical post-purchase page.
 * The new /fundadores/obrigado page handles Stripe session_id polling.
 * permanentRedirect uses HTTP 308 in Next.js App Router (permanent, preserves method).
 */
export default function FoundingObrigadoPage() {
  permanentRedirect('/fundadores/obrigado');
}
