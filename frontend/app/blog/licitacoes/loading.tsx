/**
 * Loading boundary for /blog/licitacoes route + children.
 * PSEO-005: Shows branded skeleton while ISR regenerates or on cold start.
 */
import { PseoLoadingSkeleton } from "@/components/seo/PseoLoadingSkeleton";

export default function Loading() {
  return <PseoLoadingSkeleton layout="hero+stats" />;
}
