/**
 * TestimonialsBlock — Social proof / depoimentos for use-case landing pages
 *
 * RSC with a 2x2 grid of testimonial cards. Content varies by use case.
 */
interface Testimonial {
  quote: string;
  author: string;
  role: string;
  company: string;
}

interface TestimonialsBlockProps {
  title: string;
  subtitle: string;
  testimonials: Testimonial[];
}

export default function TestimonialsBlock({ title, subtitle, testimonials }: TestimonialsBlockProps) {
  return (
    <section className="py-16">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 className="text-3xl sm:text-4xl font-bold text-ink text-center mb-4">
          {title}
        </h2>
        <p className="text-lg text-ink-secondary text-center max-w-2xl mx-auto mb-12">
          {subtitle}
        </p>

        <div className="grid sm:grid-cols-2 gap-6">
          {testimonials.map((t, i) => (
            <div
              key={i}
              className="bg-surface-0 border border-[color:var(--border)] rounded-xl p-6 hover:shadow-md transition-shadow"
            >
              <svg
                className="w-6 h-6 text-brand-blue/30 mb-3"
                fill="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path d="M4.583 17.321C3.553 16.227 3 15 3 13.011c0-3.5 2.457-6.637 6.03-8.188l.893 1.378c-3.335 1.804-3.987 4.145-4.247 5.621.537-.278 1.24-.375 1.929-.311C9.591 11.69 11 13.163 11 15c0 2.21-1.79 4-4 4-1.2 0-2.12-.537-2.907-1.315l.49-.364zM14.583 17.321C13.553 16.227 13 15 13 13.011c0-3.5 2.457-6.637 6.03-8.188l.893 1.378c-3.335 1.804-3.987 4.145-4.247 5.621.537-.278 1.24-.375 1.929-.311C19.591 11.69 21 13.163 21 15c0 2.21-1.79 4-4 4-1.2 0-2.12-.537-2.907-1.315l.49-.364z" />
              </svg>
              <blockquote className="text-sm text-ink-secondary mb-4 leading-relaxed">
                &ldquo;{t.quote}&rdquo;
              </blockquote>
              <div>
                <p className="font-semibold text-sm text-ink">{t.author}</p>
                <p className="text-xs text-ink-muted">{t.role}, {t.company}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
