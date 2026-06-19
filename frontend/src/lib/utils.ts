// Feature: All features (cross-cutting utilities)
// Layer:   Lib
// Purpose: Shared utility functions used across all frontend components.
// API:     None

import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(amount: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(amount)
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(
    typeof date === "string" ? new Date(date) : date
  )
}

export function formatRelativeDate(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
  if (diffDays === 0) return "Today"
  if (diffDays === 1) return "Yesterday"
  if (diffDays < 7) return `${diffDays} days ago`
  return formatDate(d)
}

// Brand-logo fallback chain. Clearbit's logo API is dead (returns blank images), so we
// ignore those URLs and fetch real icons from Google's favicon service, then DuckDuckGo.
// A real uploaded logo (any non-clearbit url) is preferred. Empty array → show initials.
export function brandLogoSources(url?: string | null, website?: string | null): string[] {
  const domain = website ? website.replace(/^https?:\/\//, "").replace(/\/.*$/, "") : null
  const uploaded = url && !url.includes("clearbit.com") ? url : null
  return [
    uploaded,
    domain ? `https://www.google.com/s2/favicons?domain=${domain}&sz=128` : null,
    domain ? `https://icons.duckduckgo.com/ip3/${domain}.ico` : null,
  ].filter(Boolean) as string[]
}
