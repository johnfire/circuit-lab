import { activeLocale } from './localization.ts';

export function formatMeasurement(value: number, options: Intl.NumberFormatOptions = {}): string {
  return new Intl.NumberFormat(activeLocale(), { useGrouping: false, maximumSignificantDigits: 4, ...options }).format(value);
}

export function formatTimestamp(timestamp: string): string {
  const instant = new Date(timestamp);
  return Number.isNaN(instant.getTime()) ? timestamp
    : new Intl.DateTimeFormat(activeLocale(), { dateStyle: 'medium', timeStyle: 'short' }).format(instant);
}
