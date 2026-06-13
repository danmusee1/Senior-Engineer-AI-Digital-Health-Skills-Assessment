"use client";
import { useState, useRef, useEffect } from "react";
import Link from "next/link";


const apiUrl = process.env.NEXT_PUBLIC_API_URL;
const API = apiUrl ;

interface Doc { id: number; filename: string; created_at: string; }
type StatusType = "success" | "error" | "loading";
interface Status { type: StatusType; message: string; }

export default function UploadPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const fetchDocs = async () => {
    try {
      const res = await fetch(`${API}/rag/documents`);
      setDocs(await res.json());
    } catch {}
  };

  useEffect(() => { fetchDocs(); }, []);

  const uploadFile = async (file: File) => {
    if (file.type !== "application/pdf") {
      setStatus({ type: "error", message: "Only PDF files are accepted." });
      return;
    }
    setStatus({ type: "loading", message: `Uploading "${file.name}"... this may take a moment.` });
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch(`${API}/rag/upload`, { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed.");
      setStatus({ type: "success", message: `"${data.filename}" ingested successfully!` });
      fetchDocs();
    } catch (e: any) {
      setStatus({ type: "error", message: e.message });
    }
  };

  const statusStyles: Record<StatusType, string> = {
    success: "bg-green-50 text-green-700 border border-green-200",
    error: "bg-red-50 text-red-700 border border-red-200",
    loading: "bg-blue-50 text-blue-700 border border-blue-200",
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-[#193946] px-8 h-14 flex items-center gap-8 shadow">
        <Link href="/" className="text-white font-bold text-lg mr-auto tracking-tight">
          Last Mile Health RAG
        </Link>
        <Link href="/upload" className="text-white font-medium text-sm border-b-2 border-white pb-0.5">
          Upload
        </Link>
        <Link href="/chat" className="text-white/80 hover:text-white font-medium text-sm transition-colors">
          Chat
        </Link>
      </nav>

      <div className="max-w-3xl mx-auto px-6 py-10 space-y-6">
        {/* Upload card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-8">
          <h1 className="text-2xl font-bold text-[#193946] mb-1">Upload PDF</h1>
          <p className="text-gray-500 mb-6">Upload a PDF to ingest it into the RAG pipeline.</p>

          <div
            className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors
              ${dragging ? "border-[#1d7689] bg-[#1d7689]/5" : "border-gray-200 hover:border-[#1d7689] hover:bg-gray-50"}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) uploadFile(f); }}
          >
            <input ref={inputRef} type="file" accept="application/pdf" className="hidden"
              onChange={(e) => e.target.files?.[0] && uploadFile(e.target.files[0])} />
            <div className="flex flex-col items-center gap-3">
              <div className="w-14 h-14 rounded-full bg-[#1d7689]/10 flex items-center justify-center">
                <svg className="w-7 h-7 text-[#1d7689]" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 16V4m0 0L8 8m4-4l4 4M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2"/>
                </svg>
              </div>
              <p className="font-semibold text-[#193946]">Click or drag a PDF here</p>
              <p className="text-sm text-gray-400">Max 20MB</p>
            </div>
          </div>

          {status && (
            <div className={`mt-4 px-4 py-3 rounded-lg text-sm font-medium ${statusStyles[status.type]}`}>
              {status.message}
            </div>
          )}
        </div>

        {/* Documents list */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-8">
          <h2 className="text-sm font-bold uppercase tracking-widest text-[#1d7689] mb-4">
            Ingested Documents
          </h2>
          {docs.length === 0 ? (
            <div className="text-center py-10 text-gray-400">
              <p>No documents ingested yet.</p>
            </div>
          ) : (
            <ul className="space-y-2">
              {docs.map((doc) => (
                <li key={doc.id} className="flex items-center gap-3 px-4 py-3 rounded-lg border border-gray-100 hover:border-[#1d7689]/30 transition-colors">
                  <span className="text-xl">📄</span>
                  <span className="font-medium text-[#193946] flex-1 text-sm">{doc.filename}</span>
                  <span className="text-xs text-gray-400">{new Date(doc.created_at).toLocaleDateString()}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
