"use client";

import { useEffect, useRef, useState } from "react";
import { askChat, type ChatSource } from "@/lib/api";

type Message =
  | { role: "user"; content: string }
  | { role: "assistant"; content: string; sources: ChatSource[] }
  | { role: "error"; content: string };

const EXAMPLE_PROMPTS = [
  "Who are the best goalkeepers based on saves and clean sheets?",
  "Tell me about a forward who scores a lot of goals.",
  "Which players stand out defensively?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async (question: string) => {
    const query = question.trim();
    if (!query || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: query }]);
    setInput("");
    setLoading(true);
    try {
      const { answer, sources } = await askChat(query);
      setMessages((prev) => [...prev, { role: "assistant", content: answer, sources }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "error",
          content: "Could not reach the chat assistant. Is the backend running with a Groq API key set?",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 max-w-2xl mx-auto h-[calc(100vh-8rem)]">
      <div>
        <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          Ask about the tournament
        </h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Ask a question in plain English. Answers are grounded in real player stats from the
          dataset — not made up.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto flex flex-col gap-4 pr-1">
        {messages.length === 0 && (
          <div className="flex flex-col gap-2 mt-2">
            <span className="text-xs uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
              Try asking
            </span>
            <div className="flex flex-col gap-2">
              {EXAMPLE_PROMPTS.map((p) => (
                <button
                  key={p}
                  onClick={() => send(p)}
                  className="text-left text-sm rounded-lg px-4 py-2.5 transition-colors"
                  style={{
                    background: "var(--surface-1)",
                    border: "1px solid var(--border-hairline)",
                    color: "var(--text-secondary)",
                  }}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <ChatBubble key={i} message={m} />
        ))}

        {loading && (
          <div className="self-start flex items-center gap-1.5 rounded-2xl rounded-bl-sm px-4 py-3"
            style={{ background: "var(--surface-1)", border: "1px solid var(--border-hairline)" }}
          >
            <Dot delay="0ms" />
            <Dot delay="150ms" />
            <Dot delay="300ms" />
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex gap-2 pb-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about players or teams..."
          disabled={loading}
          className="flex-1 rounded-full px-4 py-2.5 text-sm outline-none"
          style={{
            background: "var(--surface-1)",
            border: "1px solid var(--border-hairline)",
            color: "var(--text-primary)",
          }}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-full px-5 py-2.5 text-sm font-medium disabled:opacity-50"
          style={{ background: "var(--series-1)", color: "white" }}
        >
          Ask
        </button>
      </form>
    </div>
  );
}

function ChatBubble({ message }: { message: Message }) {
  if (message.role === "user") {
    return (
      <div
        className="self-end max-w-[85%] rounded-2xl rounded-br-sm px-4 py-2.5 text-sm"
        style={{ background: "var(--series-1)", color: "white" }}
      >
        {message.content}
      </div>
    );
  }

  if (message.role === "error") {
    return (
      <div
        className="self-start max-w-[85%] rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm"
        style={{ background: "var(--surface-1)", border: "1px solid var(--status-critical)", color: "var(--status-critical)" }}
      >
        {message.content}
      </div>
    );
  }

  return (
    <div className="self-start max-w-[85%] flex flex-col gap-2">
      <div
        className="rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm whitespace-pre-wrap"
        style={{ background: "var(--surface-1)", border: "1px solid var(--border-hairline)", color: "var(--text-primary)" }}
      >
        {message.content}
      </div>
      {message.sources.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {message.sources.map((s) => (
            <span
              key={s.player_id}
              className="text-xs rounded-full px-2.5 py-1"
              style={{ background: "var(--background)", border: "1px solid var(--border-hairline)", color: "var(--text-muted)" }}
              title={s.summary_text}
            >
              {s.player_name} · {s.team} · {s.position}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      className="w-1.5 h-1.5 rounded-full animate-bounce"
      style={{ background: "var(--text-muted)", animationDelay: delay }}
    />
  );
}
