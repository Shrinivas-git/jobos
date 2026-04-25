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
