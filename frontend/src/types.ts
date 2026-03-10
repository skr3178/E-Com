export interface TenderResult {
  bidId: string;
  bidNumber: string;
  category: string;
  quantity: string;
  startDate: string;
  endDate: string;
  ministry: string;
  department: string;
  detailUrl: string;
  isOpen: boolean;
  timeToCloseHours: number | null;
  matchedTerms: string[];
  matchScore: number;
}

export interface TenderDetail extends TenderResult {
  buyer?: string | null;
  contactEmail?: string | null;
  address?: string | null;
  url?: string | null;
  fetchedAt: string;
  rawFields: Record<string, string | null>;
}

export interface SearchResponse {
  query: string;
  expandedTerms: string[];
  suggestedKeywords: string[];
  count: number;
  results: TenderResult[];
}

export type NotificationStatus = "unknown" | "granted" | "denied";
