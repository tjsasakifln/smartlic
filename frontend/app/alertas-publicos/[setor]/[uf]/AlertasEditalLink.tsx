'use client';

import { trackPseoEvent } from '@/lib/analytics/pseo';

interface Props {
  href: string;
  editalId: string;
}

/**
 * Client wrapper around the "Ver edital →" external link.
 * Fires pseo_edital_viewed on click while preserving the server-rendered list.
 */
export default function AlertasEditalLink({ href, editalId }: Props) {
  return (
    <a
      href={href}
      target="_blank"
      rel="nofollow noopener noreferrer"
      className="inline-block mt-2 text-sm text-brand-blue hover:underline"
      onClick={() =>
        trackPseoEvent('pseo_edital_viewed', {
          source_template: 'blog_hub',
          page_url: typeof window !== 'undefined' ? window.location.href : undefined,
          edital_id: editalId,
        })
      }
    >
      Ver edital →
    </a>
  );
}
