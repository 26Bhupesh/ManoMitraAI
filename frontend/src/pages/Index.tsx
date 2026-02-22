import { useState, useEffect, useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";
import { v4 as uuidv4 } from "uuid";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import MessageList from "@/components/MessageList";
import TypingIndicator from "@/components/TypingIndicator";
import ScreeningPanel from "@/components/ScreeningPanel";
import CrisisPanel from "@/components/CrisisPanel";
import ChatInput from "@/components/ChatInput";
import { Button } from "@/components/ui/button";
import { getSessionId } from "@/lib/session";
import {
  sendChatMessage,
  startScreening,
  answerScreening,
  routeDecide,
  crisisHandle,
  sendVideoFrame,
} from "@/lib/api";
import type { AppState, ChatMessage, CrisisResponse } from "@/lib/types";

const EMOTION_BG: Record<string, string> = {
  fear: "210 65% 97%",
  sad: "210 30% 96%",
  angry: "210 40% 97%",
  happy: "30 60% 98%",
};

const Index = () => {
  const { t } = useTranslation();
  const sessionId = useRef(getSessionId()).current;
  const [appState, setAppState] = useState<AppState>("normal");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [screeningQuestion, setScreeningQuestion] = useState("");
  const [crisisData, setCrisisData] = useState<CrisisResponse | null>(null);
  const [emotionBg, setEmotionBg] = useState<string | null>(null);
  const videoIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Add a message helper
  const addMessage = useCallback(
    (role: ChatMessage["role"], text: string, emotion?: string) => {
      setMessages((prev) => [
        ...prev,
        {
          id: uuidv4(),
          role,
          text,
          emotion,
          timestamp: new Date().toISOString(),
        },
      ]);
    },
    []
  );

  // Welcome message (once on mount, in current language)
  const welcomeSentRef = useRef(false);
  useEffect(() => {
    if (welcomeSentRef.current) return;
    welcomeSentRef.current = true;
    addMessage("bot", t("welcome_message"));
  }, [addMessage, t]);

  // Subtle emotion background shift
  useEffect(() => {
    if (emotionBg) {
      document.documentElement.style.setProperty("--background", emotionBg);
    }
    return () => {
      document.documentElement.style.removeProperty("--background");
    };
  }, [emotionBg]);

  // Video frame capture (background)
  const startVideoCapture = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      const video = document.createElement("video");
      video.srcObject = stream;
      video.autoplay = true;
      video.playsInline = true;
      videoRef.current = video;

      const canvas = document.createElement("canvas");
      canvas.width = 320;
      canvas.height = 240;
      canvasRef.current = canvas;

      videoIntervalRef.current = setInterval(() => {
        const ctx = canvas.getContext("2d");
        if (ctx && video.readyState >= 2) {
          ctx.drawImage(video, 0, 0, 320, 240);
          canvas.toBlob(
            (blob) => {
              if (blob) sendVideoFrame(sessionId, blob).catch(() => {});
            },
            "image/jpeg",
            0.6
          );
        }
      }, 4000);
    } catch {
      // Webcam not available — silent fail
    }
  }, [sessionId]);

  useEffect(() => {
    startVideoCapture();
    return () => {
      if (videoIntervalRef.current) clearInterval(videoIntervalRef.current);
      if (videoRef.current?.srcObject) {
        (videoRef.current.srcObject as MediaStream)
          .getTracks()
          .forEach((t) => t.stop());
      }
    };
  }, [startVideoCapture]);

  // Handle text send
  const handleSendText = useCallback(
    async (text: string) => {
      addMessage("user", text);
      setLoading(true);
      setAppState("loading");

      try {
        const res = await sendChatMessage(sessionId, text);
        addMessage("bot", res.bot_reply, res.emotion_used);

        if (res.emotion_used && EMOTION_BG[res.emotion_used]) {
          setEmotionBg(EMOTION_BG[res.emotion_used]);
        }

        if (res.response_type === "immediate_screening") {
          setAppState("screening_prompt");
        } else {
          setAppState("normal");
        }
      } catch {
        addMessage("system", t("error_generic"));
        setAppState("normal");
      } finally {
        setLoading(false);
      }
    },
    [sessionId, addMessage, t]
  );

  // Handle audio send
  const handleSendAudio = useCallback(
    async (blob: Blob) => {
      addMessage("user", "🎤 " + t("voice_message_sent"));
      setLoading(true);
      setAppState("loading");

      try {
        const res = await sendChatMessage(sessionId, undefined, blob);
        addMessage("bot", res.bot_reply, res.emotion_used);

        if (res.emotion_used && EMOTION_BG[res.emotion_used]) {
          setEmotionBg(EMOTION_BG[res.emotion_used]);
        }

        if (res.response_type === "immediate_screening") {
          setAppState("screening_prompt");
        } else {
          setAppState("normal");
        }
      } catch {
        addMessage("system", t("error_generic"));
        setAppState("normal");
      } finally {
        setLoading(false);
      }
    },
    [sessionId, addMessage, t]
  );

  // Start screening flow
  const handleStartScreening = useCallback(async () => {
    setLoading(true);
    try {
      const res = await startScreening(sessionId);
      setScreeningQuestion(res.question);
      setAppState("screening");
    } catch {
      addMessage("system", t("error_screening_start"));
      setAppState("normal");
    } finally {
      setLoading(false);
    }
  }, [sessionId, addMessage, t]);

  // When in screening_prompt, auto-start screening
  useEffect(() => {
    if (appState === "screening_prompt") {
      handleStartScreening();
    }
  }, [appState, handleStartScreening]);

  // Answer screening question
  const handleScreeningAnswer = useCallback(
    async (answer: number) => {
      setLoading(true);
      try {
        const res = await answerScreening(sessionId, answer);
        if (res.response_type === "screening_complete") {
          setAppState("routing");
          // Route decision
          const route = await routeDecide(sessionId);
          if (route.route === "crisis") {
            const crisis = await crisisHandle(sessionId);
            setCrisisData(crisis);
            setAppState("crisis");
          } else {
            addMessage("system", t("screening_complete_message"));
            setAppState("normal");
          }
        } else if (res.question) {
          setScreeningQuestion(res.question);
        }
      } catch {
        addMessage("system", t("error_screening"));
        setAppState("normal");
      } finally {
        setLoading(false);
      }
    },
    [sessionId, addMessage, t]
  );

  // Crisis continue
  const handleCrisisContinue = useCallback(() => {
    setCrisisData(null);
    addMessage("system", t("crisis_continue_message"));
    setAppState("normal");
  }, [addMessage, t]);

  const inputDisabled =
    loading || appState === "screening" || appState === "crisis";

  return (
    <div className="flex h-dvh flex-col bg-background transition-colors duration-1000">
      <Header />
      <main className="mx-auto flex w-full max-w-chat flex-1 flex-col overflow-hidden">
        <MessageList messages={messages} />
        {appState === "normal" && (
          <div className="px-4 pb-2 flex justify-end">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setAppState("screening_prompt")}
              disabled={loading}
            >
              {t("start_screening")}
            </Button>
          </div>
        )}
        {loading && <TypingIndicator />}
        {appState === "screening" && (
          <ScreeningPanel
            question={screeningQuestion}
            onAnswer={handleScreeningAnswer}
            disabled={loading}
          />
        )}
      </main>
      <ChatInput
        onSendText={handleSendText}
        onSendAudio={handleSendAudio}
        disabled={inputDisabled}
      />
      <Footer />
      {crisisData && (
        <CrisisPanel data={crisisData} onContinue={handleCrisisContinue} />
      )}
    </div>
  );
};

export default Index;
