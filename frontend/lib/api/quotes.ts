import { apiClient } from "@/lib/api/client";
import type { Quote, QuoteCreatePayload, QuoteValidationResult } from "@/types";

export async function createQuote(payload: QuoteCreatePayload = {}): Promise<Quote> {
  return apiClient.createQuote(payload);
}

export async function getQuote(quoteId: string): Promise<Quote> {
  return apiClient.getQuote(quoteId);
}

export async function validateQuote(quoteId: string): Promise<QuoteValidationResult> {
  return apiClient.validateQuote(quoteId);
}

export async function refreshQuote(quoteId: string): Promise<Quote> {
  return apiClient.refreshQuote(quoteId);
}

export async function listQuotes(): Promise<Quote[]> {
  return apiClient.listQuotes();
}
