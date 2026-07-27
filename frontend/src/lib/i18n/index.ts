import { init, locale, register } from 'svelte-i18n';

register('en', () => import('./locales/en.json'));
register('pt', () => import('./locales/pt.json'));

export type Locale = 'pt' | 'en';

const STORAGE_KEY = 'portinhola.locale';

export function setupI18n(): void {
  const saved = localStorage.getItem(STORAGE_KEY);
  init({
    fallbackLocale: 'pt',
    initialLocale: saved ?? (navigator.language.toLowerCase().startsWith('pt') ? 'pt' : 'en')
  });
}

export function setLocale(next: Locale): void {
  localStorage.setItem(STORAGE_KEY, next);
  locale.set(next);
}
