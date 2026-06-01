/**
 * HowItWorksBlock — 3-step "Como o SmartLic ajuda" block for use-case landing pages
 *
 * RSC displaying how SmartLic solves the specific use-case problem.
 * Content varies per use case via props.
 */
import AnimateOnScroll from '@/components/ui/AnimateOnScroll';

interface Step {
  number: number;
  title: string;
  description: string;
  icon: React.ReactNode;
}

interface HowItWorksBlockProps {
  title: string;
  subtitle: string;
  steps: Step[];
}

export default function HowItWorksBlock({ title, subtitle, steps }: HowItWorksBlockProps) {
  return (
    <section className="py-16 bg-surface-1">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimateOnScroll threshold={0.1}>
          <h2 className="text-3xl sm:text-4xl font-bold text-ink text-center mb-4">
            {title}
          </h2>
        </AnimateOnScroll>
        <AnimateOnScroll threshold={0.1} delay={100}>
          <p className="text-lg text-ink-secondary text-center max-w-2xl mx-auto mb-12">
            {subtitle}
          </p>
        </AnimateOnScroll>

        <div className="grid md:grid-cols-3 gap-8">
          {steps.map((step, i) => (
            <AnimateOnScroll key={i} delay={150 + i * 100}>
              <div className="bg-surface-0 p-6 rounded-xl border border-[color:var(--border)] hover:shadow-md transition-shadow h-full flex flex-col">
                <div className="w-12 h-12 bg-brand-navy text-white rounded-full flex items-center justify-center text-lg font-bold mb-4">
                  {step.number}
                </div>
                <div className="w-10 h-10 bg-brand-blue/10 rounded-lg flex items-center justify-center text-brand-blue mb-4">
                  {step.icon}
                </div>
                <h3 className="text-lg font-bold text-ink mb-2">{step.title}</h3>
                <p className="text-sm text-ink-secondary flex-1">{step.description}</p>
              </div>
            </AnimateOnScroll>
          ))}
        </div>
      </div>
    </section>
  );
}
