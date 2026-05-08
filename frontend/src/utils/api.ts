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
  pipeline_config?: { assessment_rounds: number; interview_rounds: number };
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
  scoring_factors?: Array<{ factor: string; impact: string; reason: string }>;
  hard_filters_passed?: boolean;
  hard_filter_failures?: string[];
  role_level_detected?: string;
  role_level_match?: string;
  tool_currency?: string;
  cv_narrative_style?: string;
  availability_signal?: string;
  rare_assets?: string[];
  self_reported_unverified?: string[];
  interview_flags?: string[];
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

export interface CandidateOfferResponse {
  response: 'accept' | 'reject';
  reason?: string | null;
  responded_at: string;
}

export interface ResponseTracking {
  status: string;
  submitted_at?: string;
  reminder_count: number;
  last_reminder_at?: string;
}

export interface PipelineRecord {
  jd_id: string;
  candidate_id: string;
  current_stage: string;
  planned_stages?: string[];
  stages: PipelineStageEntry[];
  on_hold?: boolean;
  on_hold_reason?: string;
  offer_token?: string;
  candidate_response?: CandidateOfferResponse | null;
  response_tracking?: {
    form_submitted?: ResponseTracking;
    interview_availability?: ResponseTracking;
    interest_confirmation?: ResponseTracking;
    offer_acceptance?: ResponseTracking;
    client_feedback?: ResponseTracking;
  };
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

// ── Document Vault ──────────────────────────────────────────────────────────

export type DocType = 'experience' | 'education' | 'licence' | 'identity' | 'salary';

export interface VaultDocument {
  doc_id: string;
  candidate_id: string;
  doc_type: DocType;
  tier_required: number;
  original_filename: string;
  consent_given: boolean;
  consent_timestamp: string;
  access_revoked: boolean;
  revoked_at: string | null;
  uploaded_at: string;
}

export interface DocumentListResponse {
  candidate_id: string;
  jd_id: string;
  unlocked_tier: number;
  documents: VaultDocument[];
}

export interface AccessLogEntry {
  log_id: string;
  doc_id: string;
  candidate_id: string;
  accessed_by: string;
  accessor_role: string;
  accessor_email: string;
  jd_id: string;
  access_type: 'view' | 'download';
  doc_type: string;
  tier_at_access: number;
  timestamp: string;
}

export async function uploadDocument(
  docType: string,
  consent: boolean,
  file: File,
): Promise<{ doc_id: string; doc_type: string; tier_required: number }> {
  const form = new FormData();
  form.append('doc_type', docType);
  form.append('consent', String(consent));
  form.append('file', file);
  const res = await fetch(`${API}/documents/upload`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: form,
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? 'Upload failed');
  return res.json();
}

export async function listMyDocuments(): Promise<VaultDocument[]> {
  const res = await fetch(`${API}/documents/my`, { headers: getAuthHeaders() });
  if (!res.ok) return [];
  const data = await res.json();
  return data.documents ?? [];
}

export async function listCandidateDocuments(
  candidateId: string,
  jdId: string,
): Promise<DocumentListResponse> {
  const res = await fetch(
    `${API}/documents/list?candidate_id=${encodeURIComponent(candidateId)}&jd_id=${encodeURIComponent(jdId)}`,
    { headers: getAuthHeaders() },
  );
  if (!res.ok) throw new Error((await res.json()).detail ?? 'Failed to load documents');
  return res.json();
}

export async function revokeDocumentConsent(
  docId: string,
): Promise<{ ok: boolean; message: string }> {
  const res = await fetch(`${API}/documents/${encodeURIComponent(docId)}/consent`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? 'Revoke failed');
  return res.json();
}

export async function fetchDocumentBlob(
  docId: string,
  jdId: string,
  mode: 'view' | 'download',
): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(
    `${API}/documents/${encodeURIComponent(docId)}/${mode}?jd_id=${encodeURIComponent(jdId)}`,
    { headers: getAuthHeaders() },
  );
  if (!res.ok) throw new Error((await res.json()).detail ?? 'Failed to fetch document');
  const disposition = res.headers.get('content-disposition') ?? '';
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : `${docId}.pdf`;
  return { blob: await res.blob(), filename };
}

export async function getAccessLog(params: {
  candidateId?: string;
  docId?: string;
  limit?: number;
}): Promise<{ total: number; logs: AccessLogEntry[] }> {
  const q = new URLSearchParams();
  if (params.candidateId) q.set('candidate_id', params.candidateId);
  if (params.docId) q.set('doc_id', params.docId);
  if (params.limit) q.set('limit', String(params.limit));
  const res = await fetch(`${API}/documents/access-log?${q}`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error((await res.json()).detail ?? 'Failed to load access log');
  return res.json();
}

// ── CRM ──────────────────────────────────────────────────────────────────────

export interface CrmMessage {
  id: string;
  message_id: string;
  jd_id: string;
  candidate_id: string;
  candidate_email: string;
  candidate_name: string;
  jd_title: string;
  subject: string;
  body: string;
  status: 'draft' | 'sent' | 'failed';
  created_by: string;
  created_at: string;
  approved_at: string | null;
  sent_at: string | null;
  edited: boolean;
}

export async function draftCrmMessage(jd_id: string, candidate_id: string): Promise<CrmMessage> {
  const res = await fetch(`${API}/crm/draft`, {
    method: 'POST',
    headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ jd_id, candidate_id }),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? 'Draft failed');
  return res.json();
}

export async function listCrmMessages(jd_id?: string, status?: string): Promise<CrmMessage[]> {
  const q = new URLSearchParams();
  if (jd_id) q.set('jd_id', jd_id);
  if (status) q.set('status', status);
  const res = await fetch(`${API}/crm/messages?${q}`, { headers: getAuthHeaders() });
  if (!res.ok) return [];
  return res.json();
}

export async function approveAndSendCrmMessage(
  message_id: string,
  subject?: string,
  body?: string,
): Promise<CrmMessage> {
  const res = await fetch(`${API}/crm/messages/${encodeURIComponent(message_id)}/approve`, {
    method: 'POST',
    headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ subject, body }),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? 'Send failed');
  return res.json();
}

// ── Recruiter Tasks ───────────────────────────────────────────────────────────

export type TaskType = 'call' | 'follow_up' | 'document_request' | 'interview' | 'reminder' | 'custom';
export type TaskPriority = 'low' | 'medium' | 'high';
export type CallOutcome = 'connected' | 'no_answer' | 'callback_requested';

export interface RecruiterTask {
  task_id: string;
  type: TaskType;
  description: string;
  owner_id: string;
  jd_id: string | null;
  candidate_id: string | null;
  priority: TaskPriority;
  due_at: string;
  completed_at: string | null;
  created_at: string;
  created_by: string;
  notes: string | null;
  call_outcome: CallOutcome | null;
  call_duration_mins: number | null;
}

export async function listTasks(params?: {
  owner_me?: boolean;
  overdue?: boolean;
  jd_id?: string;
  candidate_id?: string;
  completed?: boolean;
  task_type?: string;
}): Promise<RecruiterTask[]> {
  const q = new URLSearchParams();
  if (params?.owner_me) q.set('owner_me', 'true');
  if (params?.overdue) q.set('overdue', 'true');
  if (params?.jd_id) q.set('jd_id', params.jd_id);
  if (params?.candidate_id) q.set('candidate_id', params.candidate_id);
  if (params?.completed != null) q.set('completed', String(params.completed));
  if (params?.task_type) q.set('task_type', params.task_type);
  const res = await fetch(`${API}/tasks/?${q}`, { headers: getAuthHeaders() });
  if (!res.ok) return [];
  return res.json();
}

export async function createTask(data: {
  type?: TaskType;
  description: string;
  jd_id?: string;
  candidate_id?: string;
  priority?: TaskPriority;
  due_at: string;
  notes?: string;
}): Promise<RecruiterTask> {
  const res = await fetch(`${API}/tasks/`, {
    method: 'POST',
    headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? 'Create failed');
  return res.json();
}

export async function completeTask(task_id: string): Promise<RecruiterTask> {
  const res = await fetch(`${API}/tasks/${encodeURIComponent(task_id)}`, {
    method: 'PATCH',
    headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ completed: true }),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? 'Update failed');
  return res.json();
}

export async function deleteTask(task_id: string): Promise<void> {
  await fetch(`${API}/tasks/${encodeURIComponent(task_id)}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
}

export async function logCall(data: {
  jd_id?: string;
  candidate_id?: string;
  outcome: CallOutcome;
  duration_mins?: number;
  notes?: string;
}): Promise<RecruiterTask> {
  const res = await fetch(`${API}/tasks/calls`, {
    method: 'POST',
    headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? 'Log failed');
  return res.json();
}

export async function listCalls(params?: {
  jd_id?: string;
  candidate_id?: string;
}): Promise<RecruiterTask[]> {
  const q = new URLSearchParams();
  if (params?.jd_id) q.set('jd_id', params.jd_id);
  if (params?.candidate_id) q.set('candidate_id', params.candidate_id);
  const res = await fetch(`${API}/tasks/calls/list?${q}`, { headers: getAuthHeaders() });
  if (!res.ok) return [];
  return res.json();
}

// ── Analytics ─────────────────────────────────────────────────────────────────

export interface FunnelStage {
  stage: string;
  current_count: number;
  reached_count: number;
  breach_count: number;
  conversion_pct: number;
}

export interface PipelineHealth {
  total_active: number;
  sla_breach_total: number;
  funnel: FunnelStage[];
}

export interface RecruiterPerf {
  recruiter_id: string;
  recruiter_name: string;
  total_tasks: number;
  completed_tasks: number;
  overdue_tasks: number;
  avg_days_to_complete: number | null;
  completion_rate: number;
}

export interface JDFill {
  jd_id: string;
  title: string;
  status: string;
  created_at: string | null;
  filled_at: string | null;
  days_to_fill: number | null;
}

export interface TimeToFillSummary {
  avg_days: number | null;
  min_days: number | null;
  max_days: number | null;
  filled_count: number;
  total_jds: number;
  open_count: number;
}

export interface TimeToFill {
  summary: TimeToFillSummary;
  jds: JDFill[];
}

export async function getPipelineHealth(): Promise<PipelineHealth | null> {
  try {
    const res = await fetch(`${API}/analytics/pipeline-health`, { headers: getAuthHeaders() });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function getRecruiterPerformance(): Promise<RecruiterPerf[]> {
  try {
    const res = await fetch(`${API}/analytics/recruiter-performance`, { headers: getAuthHeaders() });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function getTimeToFill(): Promise<TimeToFill | null> {
  try {
    const res = await fetch(`${API}/analytics/time-to-fill`, { headers: getAuthHeaders() });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
