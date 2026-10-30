export type PredictionLabel = 'inconclusive' | 'evidence' | 'NEI';
export type VerificationStatus = 'not_implemented' | 'inconclusive' | 'completed' | 'error';
export type EvidenceSource = 'PubMed' | 'ClinicalTrials.gov';

export interface HealthResponse { status: string; api: string; model: string; evidence_sources: string; }
export interface VerificationRequest { claim: string; max_evidence_items?: number; }
export interface EvidenceItem {
  source: EvidenceSource;
  title: string;
  abstract_or_excerpt?: string | null;
  publication_date?: string | null;
  pmid?: string | null;
  nct_id?: string | null;
  source_url?: string | null;
  study_status?: string | null;
  start_date?: string | null;
  completion_date?: string | null;
}
export interface Prediction {
  label: PredictionLabel;
  confidence?: number | null;
  label_id?: number | null;
  model_score?: number | null;
  probabilities?: Partial<Record<PredictionLabel, number>> | null;
}
export interface VerificationResponse {
  claim: string;
  prediction?: Prediction | null;
  evidence: EvidenceItem[];
  status: VerificationStatus;
  warnings: string[];
  limitations: string[];
}

export function isVerificationResponse(value: unknown): value is VerificationResponse {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const response = value as Partial<VerificationResponse>;
  return (
    typeof response.claim === 'string' &&
    typeof response.status === 'string' &&
    Array.isArray(response.evidence) &&
    Array.isArray(response.warnings) &&
    Array.isArray(response.limitations)
  );
}
