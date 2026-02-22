export type AppState = 
  | "normal" 
  | "screening_prompt" 
  | "screening" 
  | "routing" 
  | "crisis" 
  | "loading";

export type MessageRole = "user" | "bot" | "system";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  text: string;
  emotion?: string;
  timestamp: string;
}

export interface ChatResponse {
  session_id: string;
  bot_reply: string;
  emotion_used: string;
  response_type: "guided_support" | "immediate_screening";
  language: string;
  timestamp: string;
}

export interface ScreeningStartResponse {
  session_id: string;
  question_index: number;
  question: string;
}

export interface ScreeningAnswerResponse {
  session_id: string;
  question_index?: number;
  question?: string;
  response_type?: "screening_complete";
}

export interface RouteResponse {
  session_id: string;
  route: "support" | "crisis";
}

export interface CrisisResponse {
  crisis_level: "moderate" | "high";
  action: string;
  reason: string;
}
