import { useEffect, useRef } from "react";
import type { ChatMessage } from "@/lib/types";
import ChatBubble from "./ChatBubble";

interface Props {
  messages: ChatMessage[];
}

const MessageList = ({ messages }: Props) => {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex flex-1 flex-col gap-3 overflow-y-auto py-4">
      {messages.map((msg) => (
        <ChatBubble key={msg.id} message={msg} />
      ))}
      <div ref={endRef} />
    </div>
  );
};

export default MessageList;
