export type AppState = 
  | "normal" 
  | "screening_prompt" 
  | "screening" 
  | "routing" 
  | "crisis" 
  | "loading";

export type MessageRole = "user" | "bot" | "system";
export type Language = "en" | "hi" | "mr";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  text: string;
  emotion?: string;
  timestamp: string;
}

// ============ AUTHENTICATION TYPES ============
export interface User {
  id: string;
  username: string;
  name: string;
  date_of_birth: string;
  preferred_language: Language;
  emergency_contact_name: string;
  emergency_contact_number: string;
  emergency_contact_relation: string;
  created_at: string;
}

export interface RegisterRequest {
  name: string;
  username: string;
  password: string;
  date_of_birth: string;
  preferred_language: Language;
  emergency_contact_name: string;
  emergency_contact_number: string;
  emergency_contact_relation: string;
}

export interface AuthResponse {
  success: boolean;
  message: string;
  session_id?: string;
  user_id?: string;
  username?: string;
  preferred_language?: Language;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

// ============ CHAT TYPES ============
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
