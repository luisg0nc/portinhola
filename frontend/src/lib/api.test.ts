import { expect, it, vi } from 'vitest';

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

import { goto } from '$app/navigation';
import { api } from './api';

it('passes through successful responses', async () => {
  globalThis.fetch = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
  const res = await api('/api/settings');
  expect(res.status).toBe(200);
  expect(goto).not.toHaveBeenCalled();
});

it('redirects to /login on 401 for non-auth endpoints', async () => {
  globalThis.fetch = vi.fn().mockResolvedValue(new Response('', { status: 401 }));
  await api('/api/settings');
  expect(goto).toHaveBeenCalledWith('/login');
});

it('does not redirect on 401 from auth endpoints', async () => {
  vi.mocked(goto).mockClear();
  globalThis.fetch = vi.fn().mockResolvedValue(new Response('', { status: 401 }));
  await api('/api/auth/login', { method: 'POST' });
  expect(goto).not.toHaveBeenCalled();
});
