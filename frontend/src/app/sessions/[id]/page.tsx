"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Copy, User, Bot, Wrench, Brain } from "lucide-react";

interface SessionDetail { session_id: string; project_path: string; message_count: number; user_count: number; assistant_count: number; first_message: string; started_at: string; model: string; file_size: number; custom_title: string; category: string; importance: number; }
interface Message { line: number; type: string; timestamp: number | string; preview: string; has_tool_use: boolean; has_thinking: boolean; }

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

  useEffect(() => { fetch(`/api/sessions/${sessionId}`).then((r) => r.json()).then(setSession); }, [sessionId]);

  const loadMessages = useCallback(() => {
    fetch(`/api/sessions/${sessionId}/messages?page=${page}&per_page=50`).then((r) => r.json()).then((d) => { setMessages(d.messages || []); setTotalMessages(d.total || 0); });
  }, [sessionId, page]);

  useEffect(() => { loadMessages(); }, [loadMessages]);

  const handleClone = async () => {
    if (!cloneName.trim()) return;
    const res = await fetch("/api/clone", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sessionId, thread_name: cloneName }) });
    const data = await res.json();
    if (data.created) { setCloneResult(`Created: ${data.filename}`); setCloning(false); } else { setCloneResult(`Error: ${data.detail || "unknown"}`); }
  };

  if (!session) return <div className="p-8 text-[var(--color-fg-subtle)]">Loading session...</div>;
  const totalPages = Math.ceil(totalMessages / 50);

  return (
    <div className="max-w-4xl">
      <Link href="/sessions" className="text-sm text-[var(--color-accent)] hover:underline flex items-center gap-1 mb-3">
        <ArrowLeft className="w-3 h-3" /> Sessions
      </Link>

      <div className="flex items-start justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold text-[var(--color-fg-default)]">
            {session.custom_title || `Session ${sessionId.slice(0, 8)}...`}
          </h1>
          <div className="flex flex-wrap gap-3 text-xs text-[var(--color-fg-subtle)] mt-1">
            <span>{session.started_at ? new Date(session.started_at).toLocaleString() : "?"}</span>
            <span>{session.message_count} messages ({session.user_count} user, {session.assistant_count} assistant)</span>
            <span>{session.model || "?"}</span>
            <span>{(session.file_size / 1024 / 1024).toFixed(1)}MB</span>
          </div>
        </div>
        <button onClick={() => setCloning(!cloning)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--color-accent)] text-white rounded-md text-sm hover:bg-[var(--color-accent-emphasis)] transition-colors">
          <Copy className="w-3.5 h-3.5" /> Clone to Thread
        </button>
      </div>

      {cloning && (
        <div className="border border-[var(--color-accent)] rounded-md p-3 mb-4 bg-[#ddf4ff]">
          <p className="text-xs text-[var(--color-fg-muted)] mb-2">Extract context into a resumable thread file.</p>
          <div className="flex gap-2">
            <input value={cloneName} onChange={(e) => setCloneName(e.target.value)} placeholder="Thread name"
              className="flex-1 px-3 py-1.5 border border-[var(--color-border)] rounded-md text-sm focus:outline-none focus:border-[var(--color-accent)]" />
            <button onClick={handleClone} disabled={!cloneName.trim()}
              className="px-4 py-1.5 bg-[var(--color-accent)] text-white rounded-md text-sm disabled:opacity-40">Clone</button>
          </div>
        </div>
      )}

      {cloneResult && (
        <div className="border border-[#aceebb] rounded-md px-3 py-2 mb-4 bg-[#dafbe1] text-sm text-[var(--color-success)]">{cloneResult}</div>
      )}

      {session.first_message && (
        <div className="border border-[var(--color-border)] rounded-md px-3 py-2 mb-4 bg-[var(--color-bg-subtle)]">
          <span className="text-[10px] text-[var(--color-fg-subtle)] uppercase tracking-wider font-medium">First prompt</span>
          <p className="text-sm text-[var(--color-fg-default)] mt-0.5">{session.first_message}</p>
        </div>
      )}

      {/* Messages */}
      <div className="space-y-2">
        {messages.map((m) => (
          <div key={m.line} className={`rounded-md px-3 py-2.5 border ${m.type === "user" ? "bg-[#ddf4ff] border-[#54aeff66]" : "bg-white border-[var(--color-border)]"}`}>
            <div className="flex items-center gap-2 mb-1">
              {m.type === "user" ? <User className="w-3.5 h-3.5 text-[var(--color-accent)]" /> : <Bot className="w-3.5 h-3.5 text-[var(--color-done)]" />}
              <span className="text-[10px] text-[var(--color-fg-subtle)] uppercase tracking-wider font-medium">{m.type}</span>
              {m.has_tool_use && <Wrench className="w-3 h-3 text-[var(--color-attention)]" title="Uses tools" />}
              {m.has_thinking && <Brain className="w-3 h-3 text-[var(--color-done)]" title="Has thinking" />}
            </div>
            <p className="text-sm text-[var(--color-fg-default)] whitespace-pre-wrap">{m.preview}</p>
          </div>
        ))}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 mt-4 mb-8">
          <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
            className="px-3 py-1.5 rounded-md border border-[var(--color-border)] text-sm disabled:opacity-30 hover:bg-[var(--color-bg-subtle)]">Previous</button>
          <span className="text-sm text-[var(--color-fg-subtle)]">Page {page} / {totalPages}</span>
          <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page === totalPages}
            className="px-3 py-1.5 rounded-md border border-[var(--color-border)] text-sm disabled:opacity-30 hover:bg-[var(--color-bg-subtle)]">Next</button>
        </div>
      )}
    </div>
  );
}
