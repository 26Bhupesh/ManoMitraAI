import { motion } from "framer-motion";
import type { ChatMessage as ChatMessageType } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  message: ChatMessageType;
}

const ChatBubble = ({ message }: Props) => {
  const { role, text } = message;

  if (role === "system") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex justify-center px-4 py-1"
      >
        <p className="rounded-lg bg-chat-system px-4 py-2 text-center text-sm italic text-chat-system-foreground">
          {text}
        </p>
      </motion.div>
    );
  }

  const isUser = role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className={cn("flex px-4", isUser ? "justify-end" : "justify-start")}
    >
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "rounded-br-md bg-chat-user text-chat-user-foreground"
            : "rounded-bl-md bg-chat-bot text-chat-bot-foreground shadow-soft"
        )}
      >
        {text}
      </div>
    </motion.div>
  );
};

export default ChatBubble;
