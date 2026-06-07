// Type aliases mirror backend Pydantic Literal types. Keep in sync with
// backend/auth_service/models/schemas.py.

import type {
  AiWorkflowStatus,
  LeadContactType,
  LeadStatus,
  LeadType,
  PaymentStatus,
  ScrapeJobStatus,
  WebPresence,
  WebsiteBuildStatus,
} from "@/lib/leadEnums";

export interface Lead {
  id: string;
  external_id: string;
  scrape_job_id: string | null;
  primary_source: string;
  source_url: string | null;
  lead_type: LeadType;
  category: string | null;
  business_name: string;
  name_normalized: string;
  description: string | null;
  about: string | null;
  country: string | null;
  region: string | null;
  city: string | null;
  address: string | null;
  postal_code: string | null;
  lat: number | null;
  lng: number | null;
  phone: string | null;
  email: string | null;
  website_url: string | null;
  facebook_url: string | null;
  instagram_url: string | null;
  menu_url: string | null;
  web_presence: WebPresence;
  rating: number | null;
  review_count: number | null;
  reviews: unknown[] | null;
  opening_hours: Record<string, string> | null;
  photo_urls: string[];
  website_build_status: WebsiteBuildStatus;
  ai_workflow_status: AiWorkflowStatus;
  lead_status: LeadStatus;
  lead_contact_type: LeadContactType;
  payment_status: PaymentStatus;
  ai_score: number | null;
  ai_recommendation: string | null;
  ai_reasoning: string | null;
  ai_scored_at: string | null;
  design_prompt: string | null;
  extra: Record<string, unknown>;
  closed_amount: number | null;
  closed_at: string | null;
  notes: string | null;
  languages: string[];
  created_at: string;
  updated_at: string;
}

export interface LeadsListResponse {
  items: Lead[];
  total: number;
}

export interface LeadFiltersState {
  country: string;
  city: string;
  category: string;
  web_presence: WebPresence[];
  lead_status: LeadStatus[];
  lead_type: LeadType | "";
  min_rating: string; // string for input, parsed before fetch
  max_rating: string;
  min_reviews: string;
  max_reviews: string;
  search: string;
}

export const EMPTY_FILTERS: LeadFiltersState = {
  country: "",
  city: "",
  category: "",
  web_presence: [],
  lead_status: [],
  lead_type: "",
  min_rating: "",
  max_rating: "",
  min_reviews: "",
  max_reviews: "",
  search: "",
};

// Scrape jobs — mirror backend Pydantic models.

export interface ScrapeFilters {
  min_rating: number | null;
  max_rating: number | null;
  min_reviews: number | null;
  max_reviews: number | null;
  web_presence: WebPresence[];
}

export interface ScrapeParams {
  category: string;
  country: string;
  cities: string[];
  areas: string[];
  max_results_per_area: number;
  language: string;
  lead_type: LeadType;
  with_reviews: boolean;
  review_limit: number;
  filters: ScrapeFilters;
}

export interface ScrapeJob {
  id: string;
  created_at: string;
  status: ScrapeJobStatus;
  params: ScrapeParams;
  started_at: string | null;
  finished_at: string | null;
  results_found: number | null;
  results_inserted: number | null;
  results_skipped: number | null;
  error: string | null;
  triggered_by: string;
}

export interface ConversionTimePoint {
  month: string;
  revenue: number;
  accepted: number;
  sent: number;
}

export interface ConversionBreakdownRow {
  key: string;
  accepted: number;
  revenue: number;
}

export interface ConversionSummary {
  total_sent: number;
  total_accepted: number;
  total_refused: number;
  conversion_rate: number;
  total_revenue: number;
  average_deal_size: number;
  timeseries: ConversionTimePoint[];
  by_lead_type: ConversionBreakdownRow[];
  by_category: ConversionBreakdownRow[];
  by_city: ConversionBreakdownRow[];
}

export interface ConversionFilters {
  lead_type: string;
  city: string;
  category: string;
  since: string;
}

export const EMPTY_CONVERSION_FILTERS: ConversionFilters = {
  lead_type: "",
  city: "",
  category: "",
  since: "",
};
