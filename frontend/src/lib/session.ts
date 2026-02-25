import { v4 as uuidv4 } from "uuid";
import type { Language } from "./types";

const SESSION_KEY = "manomitra_session_id";
const AUTH_KEY = "manomitra_auth";
const USER_KEY = "manomitra_user";
const LANGUAGE_KEY = "manomitra_language";

interface AuthState {
  is_authenticated: boolean;
  user_id: string | null;
  username: string | null;
  session_id: string;
}

export function getSessionId(): string {
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = uuidv4();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

export function isAuthenticated(): boolean {
  const auth = localStorage.getItem(AUTH_KEY);
  if (!auth) return false;
  try {
    const authState: AuthState = JSON.parse(auth);
    return authState.is_authenticated;
  } catch {
    return false;
  }
}

export function getAuthState(): AuthState | null {
  const auth = localStorage.getItem(AUTH_KEY);
  if (!auth) return null;
  try {
    return JSON.parse(auth);
  } catch {
    return null;
  }
}

export function setAuthenticated(
  sessionId: string,
  userId: string,
  username: string,
  language: Language
) {
  const authState: AuthState = {
    is_authenticated: true,
    user_id: userId,
    username: username,
    session_id: sessionId,
  };
  localStorage.setItem(AUTH_KEY, JSON.stringify(authState));
  localStorage.setItem(SESSION_KEY, sessionId);
  localStorage.setItem(LANGUAGE_KEY, language);
}

export function logout() {
  localStorage.removeItem(AUTH_KEY);
  localStorage.removeItem(USER_KEY);
  // Don't remove session_id - frontend generates new one on next load
}

export function getPreferredLanguage(): Language {
  const lang = localStorage.getItem(LANGUAGE_KEY);
  return (lang as Language) || "en";
}

export function setPreferredLanguage(language: Language) {
  localStorage.setItem(LANGUAGE_KEY, language);
}

