// Type aliases mirror backend Pydantic Literal types. Keep in sync with
// backend/auth_service/models/schemas.py.

import type {
  AiWorkflowStatus,
  LeadContactType,
  LeadStatus,
  LeadType,
  PaymentStatus,
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
  extra: Record<string, unknown>;
  notes: string | null;
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
