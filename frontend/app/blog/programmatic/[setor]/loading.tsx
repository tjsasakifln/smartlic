/**
 * Loading boundary for /blog/programmatic/[setor] route.
 * PSEO-005: Shows branded skeleton while ISR regenerates or on cold start.
 */
import { PseoLoadingSkeleton } from "@/components/seo/PseoLoadingSkeleton";

export default function Loading() {
  return <PseoLoadingSkeleton layout="hero+stats" />;
}
