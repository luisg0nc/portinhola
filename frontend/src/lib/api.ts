import { goto } from '$app/navigation';

export async function api(path: string, options: RequestInit = {}): Promise<Response> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options
  });
  if (res.status === 401 && !path.startsWith('/api/auth/')) {
    await goto('/login');
  }
  return res;
}
