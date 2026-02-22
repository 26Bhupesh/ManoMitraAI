import axios from "axios";
import type {
  ChatResponse,
  ScreeningStartResponse,
  ScreeningAnswerResponse,
  RouteResponse,
  CrisisResponse,
} from "./types";

const API = axios.create({
  baseURL: "http://127.0.0.1:8000",
});

export async function sendChatMessage(
  sessionId: string,
  text?: string,
  audio?: Blob
): Promise<ChatResponse> {
  const form = new FormData();
  form.append("session_id", sessionId);
  if (text) form.append("text", text);
  if (audio) form.append("audio", audio, "recording.webm");
  const { data } = await API.post<ChatResponse>("/chat/message", form);
  return data;
}

export async function sendVideoFrame(
  sessionId: string,
  frame: Blob
): Promise<void> {
  const form = new FormData();
  form.append("session_id", sessionId);
  form.append("frame", frame, "frame.jpg");
  await API.post("/video/video_frame", form);
}

export async function startScreening(
  sessionId: string
): Promise<ScreeningStartResponse> {
  const { data } = await API.post<ScreeningStartResponse>("/screening/start", {
    session_id: sessionId,
  });
  return data;
}

export async function answerScreening(
  sessionId: string,
  answer: number
): Promise<ScreeningAnswerResponse> {
  const { data } = await API.post<ScreeningAnswerResponse>("/screening/answer", {
    session_id: sessionId,
    answer,
  });
  return data;
}

export async function routeDecide(
  sessionId: string
): Promise<RouteResponse> {
  const { data } = await API.post<RouteResponse>(
    `/route/decide?session_id=${sessionId}`
  );
  return data;
}

export async function crisisHandle(
  sessionId: string
): Promise<CrisisResponse> {
  const { data } = await API.post<CrisisResponse>(
    `/crisis/handle?session_id=${sessionId}`
  );
  return data;
}
