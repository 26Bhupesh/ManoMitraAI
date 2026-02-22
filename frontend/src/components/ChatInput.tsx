import { useState, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Send, Mic, MicOff } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  onSendText: (text: string) => void;
  onSendAudio: (blob: Blob) => void;
  disabled: boolean;
}

const ChatInput = ({ onSendText, onSendAudio, disabled }: Props) => {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const [recording, setRecording] = useState(false);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    onSendText(trimmed);
    setText("");
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const toggleRecording = async () => {
    if (recording && mediaRef.current) {
      mediaRef.current.stop();
      setRecording(false);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => chunksRef.current.push(e.data);
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        onSendAudio(blob);
        stream.getTracks().forEach((t) => t.stop());
      };
      recorder.start();
      mediaRef.current = recorder;
      setRecording(true);
    } catch {
      console.error("Microphone access denied");
    }
  };

  return (
    <div className="border-t border-border bg-card/80 backdrop-blur-md px-4 py-3">
      <div className="mx-auto flex max-w-chat items-end gap-2">
        <button
          onClick={toggleRecording}
          disabled={disabled}
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition-colors",
            recording
              ? "bg-destructive text-destructive-foreground"
              : "bg-muted text-muted-foreground hover:bg-muted/80"
          )}
          aria-label={
            recording ? t("aria_stop_recording") : t("aria_start_recording")
          }
        >
          {recording ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
        </button>

        <div className="relative flex-1">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKey}
            disabled={disabled}
            placeholder={t("input_placeholder")}
            rows={1}
            className="w-full resize-none rounded-2xl border border-border bg-background px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
          />
        </div>

        <button
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          aria-label={t("aria_send_message")}
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

export default ChatInput;
