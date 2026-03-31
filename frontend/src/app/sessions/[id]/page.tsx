"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Copy, User, Bot, Wrench, Brain, ChevronDown, ChevronRight } from "lucide-react";

interface SessionDetail {
  session_id: string;
  project_path: string;
  message_count: number;
  user_count: number;
  assistant_count: number;
  first_message: string;
  started_at: string;
  model: string;
  file_size: number;
}

interface Message {
  line: number;
  type: string;
  timestamp: number | string;
  preview: string;
  has_tool_use: boolean;
  has_thinking: boolean;
  model?: string;
}

export default function SessionDetailPage() {
  const params = useParams();
  const sessionId = params.id as string;

  const [session, setSession] = useState<SessionDetail | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [page, setPage] = useState(1);
  const [totalMessages, setTotalMessages] = useState(0);
  const [cloning, setCloning] = useState(false);
  const [cloneName, setCloneName] = useState("");
  const [cloneResult, setCloneResult] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/sessions/${sessionId}`).then((r) => r.json()).then(setSession);
  }, [sessionId]);

  const loadMessages = useCallback(() => {
    fetch(`/api/sessions/${sessionId}/messages?page=${page}&per_page=50`)
      .then((r) => r.json())
      .then((d) => {
        setMessages(d.messages || []);
        setTotalMessages(d.total || 0);
      });
  }, [sessionId, page]);

  useEffect(() => { loadMessages(); }, [loadMessages]);

  const handleClone = async () => {
    if (!cloneName.trim()) return;
    const res = await fetch("/api/clone", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, thread_name: cloneName }),
    });
    const data = await res.json();
    if (data.created) {
      setCloneResult(`Created: ${data.filename}`);
      setCloning(false);
    } else {
      setCloneResult(`Error: ${data.detail || "unknown"}`);
    }
  };

  if (!session) {
    return <div className="animate-pulse text-zinc-500 p-8">Loading session...</div>;
  }

  const totalPages = Math.ceil(totalMessages / 50);

  return (
    <div className="max-w-4xl">
      {/* Header */}
      <div className="mb-6">
        <Link href="/sessions" className="text-zinc-500 text-sm hover:text-zinc-300 flex items-center gap-1 mb-2">
          <ArrowLeft className="w-3 h-3" /> Back to sessions
        </Link>

        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-zinc-100 mb-1">
              Session {sessionId.slice(0, 8)}...
            </h1>
            <div className="flex flex-wrap gap-3 text-xs text-zinc-500">
              <span>{session.started_at ? new Date(session.started_at).toLocaleString() : "?"}</span>
              <span>{session.message_count} messages ({session.user_count} user, {session.assistant_count} assistant)</span>
              <span>{session.model || "unknown model"}</span>
              <span>{(session.file_size / 1024 / 1024).toFixed(1)}MB</span>
            </div>
          </div>

          <button
            onClick={() => setCloning(!cloning)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-violet-600 text-white rounded-lg text-sm hover:bg-violet-500 transition-colors"
          >
            <Copy className="w-3.5 h-3.5" />
            Clone to Thread
          </button>
        </div>

        {/* Clone dialog */}
        {cloning && (
          <div className="mt-3 bg-zinc-900 border border-violet-500/30 rounded-lg p-3">
            <p className="text-zinc-400 text-xs mb-2">
              Extract context from this session and create a resumable thread file.
            </p>
            <div className="flex gap-2">
              <input
                value={cloneName}
                onChange={(e) => setCloneName(e.target.value)}
                placeholder="Thread name (e.g. motifs_discussion)"
                className="flex-1 px-3 py-1.5 bg-zinc-800 border border-zinc-700 rounded text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-violet-500"
              />
              <button
                onClick={handleClone}
                disabled={!cloneName.trim()}
                className="px-4 py-1.5 bg-violet-600 text-white rounded text-sm hover:bg-violet-500 disabled:opacity-40"
              >
                Clone
              </button>
            </div>
          </div>
        )}

        {cloneResult && (
          <div className="mt-2 bg-green-900/20 border border-green-500/30 rounded-lg px-3 py-2 text-green-400 text-sm">
            {cloneResult}
          </div>
        )}

        {/* First message preview */}
        {session.first_message && (
          <div className="mt-3 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2">
            <span className="text-zinc-600 text-[10px] uppercase tracking-wider">First prompt</span>
            <p className="text-zinc-300 text-sm mt-0.5">{session.first_message}</p>
          </div>
        )}
      </div>

      {/* Message thread */}
      <div className="space-y-2">
        {messages.map((m) => (
          <div
            key={m.line}
            className={`rounded-lg px-3 py-2.5 ${
              m.type === "user"
                ? "bg-blue-950/30 border border-blue-900/30"
                : "bg-zinc-900 border border-zinc-800"
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              {m.type === "user" ? (
                <User className="w-3.5 h-3.5 text-blue-400" />
              ) : (
                <Bot className="w-3.5 h-3.5 text-violet-400" />
              )}
              <span className="text-zinc-500 text-[10px] uppercase tracking-wider">
                {m.type}
              </span>
              {m.has_tool_use && (
                <Wrench className="w-3 h-3 text-amber-500" title="Uses tools" />
              )}
              {m.has_thinking && (
                <Brain className="w-3 h-3 text-pink-500" title="Has thinking" />
              )}
            </div>
            <p className="text-zinc-300 text-sm whitespace-pre-wrap">{m.preview}</p>
          </div>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 mt-4 mb-8">
          <button
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 rounded bg-zinc-800 text-zinc-400 text-sm disabled:opacity-30 hover:bg-zinc-700"
          >
            Previous
          </button>
          <span className="text-zinc-500 text-sm">Page {page} / {totalPages}</span>
          <button
            onClick={() => setPage(Math.min(totalPages, page + 1))}
            disabled={page === totalPages}
            className="px-3 py-1.5 rounded bg-zinc-800 text-zinc-400 text-sm disabled:opacity-30 hover:bg-zinc-700"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
