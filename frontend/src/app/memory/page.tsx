"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { FileText, Plus, Save, X, GitBranch } from "lucide-react";

interface MemoryFile {
  filename: string;
  file_size: number;
  modified_at: string;
  status: string;
  summary: string;
}

interface Project {
  encoded_path: string;
  display_name: string;
  memory_count: number;
}

export default function MemoryPage() {
  const searchParams = useSearchParams();
  const projectParam = searchParams.get("project") || "";

  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState(projectParam);
  const [files, setFiles] = useState<MemoryFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [editing, setEditing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newContent, setNewContent] = useState("");
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/projects").then((r) => r.json()).then((d) => {
      const withMemory = (d.projects || []).filter((p: Project) => p.memory_count > 0);
      setProjects(withMemory);
      if (!selectedProject && withMemory.length > 0) {
        setSelectedProject(withMemory[0].encoded_path);
      }
    });
  }, []);

  useEffect(() => {
    if (!selectedProject) return;
    fetch(`/api/memory?project=${selectedProject}`).then((r) => r.json()).then((d) => {
      setFiles(d.files || []);
    });
  }, [selectedProject]);

  const loadFile = (filename: string) => {
    setSelectedFile(filename);
    setEditing(false);
    fetch(`/api/memory/${selectedProject}/${filename}`).then((r) => r.json()).then((d) => {
      setContent(d.content || "");
    });
  };

  const saveFile = async () => {
    const res = await fetch(`/api/memory/${selectedProject}/${selectedFile}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    if (res.ok) {
      setSaveStatus("Saved");
      setEditing(false);
      setTimeout(() => setSaveStatus(null), 2000);
    }
  };

  const createFile = async () => {
    if (!newName.trim()) return;
    const res = await fetch(`/api/memory/${selectedProject}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: newName, content: newContent }),
    });
    if (res.ok) {
      setCreating(false);
      setNewName("");
      setNewContent("");
      // Refresh
      const d = await fetch(`/api/memory?project=${selectedProject}`).then((r) => r.json());
      setFiles(d.files || []);
    }
  };

  const statusColor = (s: string) => {
    switch (s) {
      case "active": return "bg-green-900/40 text-green-400";
      case "paused": return "bg-amber-900/40 text-amber-400";
      case "merged": return "bg-blue-900/40 text-blue-400";
      case "archived": return "bg-zinc-800 text-zinc-500";
      default: return "bg-zinc-800 text-zinc-500";
    }
  };

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-zinc-100">Memory Files</h1>
        <div className="flex gap-2">
          <select
            value={selectedProject}
            onChange={(e) => { setSelectedProject(e.target.value); setSelectedFile(null); }}
            className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm text-zinc-200"
          >
            {projects.map((p) => (
              <option key={p.encoded_path} value={p.encoded_path}>
                {p.display_name} ({p.memory_count})
              </option>
            ))}
          </select>
          <button
            onClick={() => setCreating(true)}
            className="flex items-center gap-1 px-3 py-1.5 bg-violet-600 text-white rounded-lg text-sm hover:bg-violet-500"
          >
            <Plus className="w-3.5 h-3.5" /> New Thread
          </button>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        {/* File list */}
        <div className="space-y-1.5">
          {files.map((f) => (
            <button
              key={f.filename}
              onClick={() => loadFile(f.filename)}
              className={`w-full text-left rounded-lg px-3 py-2 transition-colors ${
                selectedFile === f.filename
                  ? "bg-violet-600/20 border border-violet-500/30"
                  : "bg-zinc-900 border border-zinc-800 hover:border-zinc-600"
              }`}
            >
              <div className="flex items-center gap-2 mb-0.5">
                {f.filename.startsWith("thread_") ? (
                  <GitBranch className="w-3.5 h-3.5 text-violet-400" />
                ) : (
                  <FileText className="w-3.5 h-3.5 text-zinc-500" />
                )}
                <span className="text-zinc-200 text-sm font-medium truncate">
                  {f.filename.replace(".md", "")}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${statusColor(f.status)}`}>
                  {f.status}
                </span>
                <span className="text-zinc-600 text-[10px]">
                  {(f.file_size / 1024).toFixed(1)}KB
                </span>
              </div>
            </button>
          ))}
        </div>

        {/* Content viewer/editor */}
        <div className="md:col-span-2">
          {creating ? (
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
              <h3 className="text-zinc-200 font-semibold mb-3">Create New Thread</h3>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="thread_my_topic.md"
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded text-sm text-zinc-200 placeholder-zinc-600 mb-3 focus:outline-none focus:border-violet-500"
              />
              <textarea
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
                placeholder="# Thread: My Topic\n\n## Status: ACTIVE\n\n## Open Questions\n- ..."
                rows={12}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded text-sm text-zinc-200 placeholder-zinc-600 font-mono mb-3 focus:outline-none focus:border-violet-500"
              />
              <div className="flex gap-2">
                <button onClick={createFile} className="px-4 py-1.5 bg-violet-600 text-white rounded text-sm hover:bg-violet-500">
                  Create
                </button>
                <button onClick={() => setCreating(false)} className="px-4 py-1.5 bg-zinc-800 text-zinc-400 rounded text-sm hover:bg-zinc-700">
                  Cancel
                </button>
              </div>
            </div>
          ) : selectedFile ? (
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg">
              <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800">
                <span className="text-zinc-300 text-sm font-medium">{selectedFile}</span>
                <div className="flex items-center gap-2">
                  {saveStatus && <span className="text-green-400 text-xs">{saveStatus}</span>}
                  {editing ? (
                    <>
                      <button onClick={saveFile} className="flex items-center gap-1 px-2 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-500">
                        <Save className="w-3 h-3" /> Save
                      </button>
                      <button onClick={() => { setEditing(false); loadFile(selectedFile); }} className="px-2 py-1 bg-zinc-700 text-zinc-300 rounded text-xs hover:bg-zinc-600">
                        <X className="w-3 h-3" />
                      </button>
                    </>
                  ) : (
                    <button onClick={() => setEditing(true)} className="px-2 py-1 bg-zinc-700 text-zinc-300 rounded text-xs hover:bg-zinc-600">
                      Edit
                    </button>
                  )}
                </div>
              </div>
              {editing ? (
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  className="w-full p-3 bg-zinc-950 text-zinc-200 font-mono text-sm min-h-[500px] focus:outline-none resize-y"
                />
              ) : (
                <pre className="p-3 text-zinc-300 text-sm whitespace-pre-wrap font-mono overflow-auto max-h-[600px]">
                  {content}
                </pre>
              )}
            </div>
          ) : (
            <div className="text-zinc-600 text-center py-20">
              Select a memory file to view
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
