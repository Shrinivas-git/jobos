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
  context_bonus?: number;
  fitment_score?: number;
  reasoning?: string;
  strengths?: string[];
  gaps?: string[];
  recommendation?: string;
  rank: number;
  status: string;
  source: string;
  company_types?: string[];
  avg_team_size?: string;
  role_type?: string;
  preferred_company_type?: string[];
  preferred_team_size?: string;
  jd_role_type?: string;
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

export interface CandidateProfile {
  candidate_id: string;
  name?: string;
  email?: string;
  phone?: string;
  skills?: string[];
  experience_years?: number;
  location?: string;
  notice_period?: string;
  gender?: string;
  college?: string;
  projects?: Array<any>;
  achievements?: string[];
  certifications?: string[];
  education?: Array<any>;
  languages?: string[];
  status: string;
  source: string;
  file_paths: string[];
  created_at: string;
  updated_at: string;
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

export async function getMyProfile(): Promise<CandidateProfile | null> {
  try {
    const res = await fetch(`${API}/candidates/me`, { headers: getAuthHeaders() });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function updateMyProfile(data: {
  skills?: string[];
  experience_years?: number;
  notice_period?: string;
  location?: string;
  languages?: string[];
}): Promise<CandidateProfile | null> {
  try {
    const res = await fetch(`${API}/candidates/me`, {
      method: 'PUT',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export interface PipelineExtension {
  requested_at: string;
  requested_by: string;
  additional_hours: number;
  reason: string;
  approved: boolean;
  approved_until: string | null;
  approved_by: string | null;
  approved_at: string | null;
}

export interface PipelineStageEntry {
  name: string;
  entered_at: string;
  sla_hours: number;
  due_at: string;
  warned_at: string | null;
  escalated_at: string | null;
  completed_at: string | null;
  extension: PipelineExtension | null;
}

export interface PipelineRecord {
  jd_id: string;
  candidate_id: string;
  current_stage: string;
  stages: PipelineStageEntry[];
  created_at: string;
  updated_at: string;
}

export interface PipelineBreach {
  jd_id: string;
  candidate_id: string;
  stage: string;
  due_at: string;
  escalated: boolean;
}
