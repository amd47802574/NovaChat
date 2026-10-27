import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useSessionStore } from './sessions';
import api from '@/utils/api';

vi.mock('@/utils/api', () => ({
  default: {
    get: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
  },
}));

const flushPromises = () => new Promise((resolve) => setTimeout(resolve, 0));

const seedSessions = () => {
  const store = useSessionStore();
  store.sessions = [
    { session_id: 'a', title: 'A', pinned: false, message_count: 1, updated_at: '2026-01-01T00:00:00+00:00' },
    { session_id: 'b', title: 'B', pinned: true, message_count: 2, updated_at: '2026-01-02T00:00:00+00:00' },
    { session_id: 'c', title: 'C', pinned: false, message_count: 3, updated_at: '2026-01-03T00:00:00+00:00' },
  ];
  return store;
};

describe('session store batch delete', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(api.delete).mockReset();
  });

  it('sends a batch delete request with the selected session ids', async () => {
    const store = seedSessions();
    vi.mocked(api.delete).mockResolvedValue({ data: { deleted_count: 2, message: 'ok' } });

    await store.deleteSessions(['a', 'c']);

    expect(api.delete).toHaveBeenCalledWith('/sessions/batch', {
      data: { session_ids: ['a', 'c'] },
    });
  });

  it('removes the deleted sessions from local state', async () => {
    const store = seedSessions();
    vi.mocked(api.delete).mockResolvedValue({ data: { deleted_count: 2, message: 'ok' } });

    const deleted = await store.deleteSessions(['a', 'c']);

    expect(deleted).toBe(2);
    expect(store.sessions.map((s) => s.session_id)).toEqual(['b']);
  });

  it('returns early without a request when no ids are provided', async () => {
    const store = seedSessions();

    const deleted = await store.deleteSessions([]);

    expect(deleted).toBe(0);
    expect(api.delete).not.toHaveBeenCalled();
    expect(store.sessions).toHaveLength(3);
  });

  it('keeps local state intact when the request fails', async () => {
    const store = seedSessions();
    vi.mocked(api.delete).mockRejectedValue({
      response: { data: { detail: '批量删除会话失败' } },
    });

    await expect(store.deleteSessions(['a'])).rejects.toThrow('批量删除会话失败');
    expect(store.sessions.map((s) => s.session_id)).toEqual(['a', 'b', 'c']);
  });

  it('falls back to the requested count when the server omits deleted_count', async () => {
    const store = seedSessions();
    vi.mocked(api.delete).mockResolvedValue({ data: { message: 'ok' } });

    const deleted = await store.deleteSessions(['b']);
    expect(deleted).toBe(1);
    expect(store.sessions.map((s) => s.session_id)).toEqual(['a', 'c']);
  });

  it('awaits the request so callers can clean up related caches', async () => {
    const store = seedSessions();
    let resolved = false;
    vi.mocked(api.delete).mockImplementation(async () => {
      await flushPromises();
      resolved = true;
      return { data: { deleted_count: 3, message: 'ok' } };
    });

    await store.deleteSessions(['a', 'b', 'c']);

    expect(resolved).toBe(true);
    expect(store.sessions).toHaveLength(0);
  });
});
