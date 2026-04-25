import keycloak from '../keycloak';

export const API = 'http://localhost:8000';

export function getAuthHeaders(): { Authorization: string } {
  return { Authorization: `Bearer ${keycloak.token}` };
}

export interface JD {
  jd_id: string;
  title: string;
  status: string;
  created_at: string;
}

export interface MatchResult {
  jd_id: string;
  candidate_id: string;
  match_score: number;
  composite_score?: number;
  completeness_score?: number;
  fitment_score?: number;
  reasoning?: string;
  strengths?: string[];
  gaps?: string[];
  recommendation?: string;
  rank: number;
  status: string;
  source: string;
}

export type CandidateLookup = Record<string, string>;

export interface Notification {
  notification_id: string;
  type: string;
  title: string;
  body: string;
  is_read: boolean;
  created_at: string;
  data?: {
    jd_id: string;
    jd_title: string;
    pool_size: number;
    internal_count: number;
    external_count: number;
  };
}

export async function getUnreadCount(): Promise<number> {
  try {
    const res = await fetch(`${API}/notifications/unread-count`, { headers: getAuthHeaders() });
    if (!res.ok) return 0;
    const data = await res.json();
    return data.count ?? 0;
  } catch {
    return 0;
  }
}

export async function listNotifications(): Promise<Notification[]> {
  try {
    const res = await fetch(`${API}/notifications/`, { headers: getAuthHeaders() });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function markNotificationRead(id: string): Promise<void> {
  await fetch(`${API}/notifications/${id}/read`, { method: 'PUT', headers: getAuthHeaders() });
}

export async function markAllRead(): Promise<void> {
  await fetch(`${API}/notifications/read-all`, { method: 'PUT', headers: getAuthHeaders() });
}
