import { expect, it } from 'vitest';
import { formatCents } from './money';

it('formats cents as euros in pt', () => {
  const s = formatCents(1060, 'pt');
  expect(s).toContain('10,60');
  expect(s).toContain('€');
});

it('formats cents as euros in en', () => {
  const s = formatCents(1060, 'en');
  expect(s).toContain('10.60');
  expect(s).toContain('€');
});

it('handles negative amounts', () => {
  expect(formatCents(-250, 'en')).toContain('2.50');
});
