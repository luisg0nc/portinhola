import { expect, it } from 'vitest';
import en from './locales/en.json';
import pt from './locales/pt.json';

function keys(obj: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === 'object' && v !== null
      ? keys(v as Record<string, unknown>, `${prefix}${k}.`)
      : [`${prefix}${k}`]
  );
}

it('pt and en catalogs have identical key sets', () => {
  expect(keys(en).sort()).toEqual(keys(pt).sort());
});

it('catalogs are non-empty', () => {
  expect(keys(pt).length).toBeGreaterThan(10);
});
