import type { Config, Event, Generation, Health, HistoryItem, Plan, Status } from './types';

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, headers: { 'Content-Type':'application/json', ...init?.headers }, cache:'no-store' });
  if (!response.ok) {
    const reason = await response.text().catch(() => '');
    throw new Error(`${response.status}: ${reason.slice(0, 120) || response.statusText}`);
  }
  return response.json() as Promise<T>;
}
export const api = {
  health: () => request<Health>('/api/health'),
  config: () => request<Config>('/api/system/config'),
  status: () => request<Status>('/api/energy/status'),
  generation: () => request<Generation>('/api/energy/generation'),
  plan: () => request<Plan | {message: string}>('/api/energy/plan'),
  events: () => request<Event[]>('/api/security/events?limit=30'),
  history: () => request<HistoryItem[]>('/api/energy/history?limit=25'),
  chat: (message: string) => request<{answer: string}>('/api/chat', { method: 'POST', body: JSON.stringify({message}) }),
};
