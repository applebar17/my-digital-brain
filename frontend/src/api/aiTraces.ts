import { apiRequest } from "./http";
import type { AIFlowTraceEventList } from "../types/aiTrace";

export function listAIFlowTraces(
  sessionId: string,
  bearerToken: string,
  options: { afterSequence?: number; limit?: number } = {}
): Promise<AIFlowTraceEventList> {
  return apiRequest<AIFlowTraceEventList>(`/debug/ai-traces/sessions/${sessionId}`, {
    query: {
      after_sequence: options.afterSequence ?? 0,
      limit: options.limit ?? 200
    },
    bearerToken
  });
}

export function clearAIFlowTraces(sessionId: string, bearerToken: string): Promise<null> {
  return apiRequest<null>(`/debug/ai-traces/sessions/${sessionId}`, {
    method: "DELETE",
    bearerToken
  });
}
