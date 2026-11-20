import english from '../../locales/en/messages.json' with { type: 'json' };
import { displayMessage, type MessageReference } from './display-message.ts';

export function parseMessage(submitted: unknown, depth = 0): MessageReference | null {
  if (depth > 6 || typeof submitted !== 'object' || submitted === null || !('key' in submitted)
    || typeof submitted.key !== 'string' || !Object.hasOwn(english, submitted.key)
    || !('values' in submitted) || typeof submitted.values !== 'object' || submitted.values === null
    || Array.isArray(submitted.values)) return null;
  const values: MessageReference['values'] = {};
  const entries = Object.entries(submitted.values);
  if (entries.length > 20) return null;
  for (const [name, value] of entries) {
    if (typeof value === 'string' && value.length <= 4000 || typeof value === 'number' && Number.isFinite(value)) values[name] = value;
    else {
      const nested = parseMessage(value, depth + 1);
      if (!nested) return null;
      values[name] = nested;
    }
  }
  return { key: submitted.key as keyof typeof english, values };
}

export function reportText(original: string, reference: unknown): string {
  const parsed = parseMessage(reference);
  return parsed ? displayMessage(parsed) : original;
}
