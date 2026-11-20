import { translate, type MessageKey } from './localization.ts';

type MessageValues = Record<string, string | number | MessageReference>;
export interface MessageReference { key: MessageKey; values: MessageValues }
export type DisplayMessage = string | MessageReference;

export function message(key: MessageKey, values: MessageValues = {}): MessageReference {
  return { key, values };
}

export function displayMessage(reference: DisplayMessage): string {
  if (typeof reference === 'string') return reference;
  const values = Object.fromEntries(Object.entries(reference.values).map(([key, value]) =>
    [key, typeof value === 'object' ? displayMessage(value) : value]));
  return translate(reference.key, values);
}

export class LocalizedFailure extends Error {
  readonly reference: MessageReference;
  constructor(key: MessageKey, values: MessageReference['values'] = {}) {
    super(displayMessage(message(key, values)));
    this.name = 'LocalizedFailure';
    this.reference = message(key, values);
  }
}

export function failureMessage(failure: Error): DisplayMessage {
  return failure instanceof LocalizedFailure ? failure.reference : failure.message;
}
