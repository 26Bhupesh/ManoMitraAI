const TypingIndicator = () => (
  <div className="flex justify-start px-4 py-1">
    <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-md bg-chat-bot px-4 py-3 shadow-soft">
      <span className="typing-dot h-2 w-2 rounded-full bg-muted-foreground" />
      <span className="typing-dot h-2 w-2 rounded-full bg-muted-foreground" />
      <span className="typing-dot h-2 w-2 rounded-full bg-muted-foreground" />
    </div>
  </div>
);

export default TypingIndicator;
