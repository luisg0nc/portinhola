export function formatCents(cents: number, locale: string): string {
  return new Intl.NumberFormat(locale === 'pt' ? 'pt-PT' : 'en-IE', {
    style: 'currency',
    currency: 'EUR'
  }).format(cents / 100);
}
