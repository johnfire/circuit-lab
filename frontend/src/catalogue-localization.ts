import { localization } from './localization.ts';

export function catalogueText(key: string, fallback: string): string {
  return localization.exists(key) ? localization.t(key) : fallback;
}

/** Display-only views; electrical graphs and the generated source indexes stay canonical. */
export function catalogueRecord<RecordType extends object>(record: RecordType, prefix: string, fields: readonly string[]): RecordType {
  const descriptors: PropertyDescriptorMap = {};
  for (const field of fields) {
    const original: unknown = Reflect.get(record, field);
    if (typeof original === 'string') descriptors[field] = {
      enumerable: true, get: () => catalogueText(prefix + '.' + field, original),
    };
  }
  return Object.defineProperties({ ...record }, descriptors);
}
