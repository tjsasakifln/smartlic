"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { PageHeader } from "../PageHeader";

/**
 * WorkspaceShell — wrapper for the workspace page with title and breadcrumb.
 *
 * B2GOPS-010 (#2020): Provides consistent layout for all workspace widgets.
 */
export function WorkspaceShell({ children }: { children: ReactNode }) {
  return (
    <div className="bg-[var(--canvas)] flex-1">
      <PageHeader title="Workspace" />

      <div className="max-w-6xl mx-auto px-4 py-6">
        {/* Breadcrumb */}
        <nav className="mb-6 text-sm text-[var(--ink-muted)]" aria-label="Breadcrumb">
          <Link href="/buscar" className="hover:text-[var(--brand-blue)] transition-colors">
            Inicio
          </Link>
          <span className="mx-2">/</span>
          <span className="text-[var(--ink)] font-medium">Workspace</span>
        </nav>

        {children}
      </div>
    </div>
  );
}
