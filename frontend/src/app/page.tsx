"use client";
import Link from "next/link";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navbar */}
      <nav className="bg-[#193946] px-8 h-14 flex items-center gap-8 shadow">
        <Link href="/" className="text-white font-bold text-lg mr-auto tracking-tight">
          Last Mile Health RAG
        </Link>
        <Link href="/upload" className="text-white/80 hover:text-white font-medium text-sm transition-colors">
          Upload
        </Link>
        <Link href="/chat" className="text-white/80 hover:text-white font-medium text-sm transition-colors">
          Chat
        </Link>
      </nav>

      <div className="max-w-3xl mx-auto px-6 py-10 space-y-6">
        {/* Hero card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-8">
          <h1 className="text-2xl font-bold text-[#193946] mb-2">
            RAG Document Q&A System
          </h1>
          <p className="text-gray-500 mb-6">
            Upload PDF documents and ask questions grounded in their content.
          </p>
          <div className="flex gap-3">
            <Link href="/upload">
              <button className="bg-[#1d7689] hover:bg-[#193946] text-white font-semibold px-5 py-2.5 rounded-lg transition-colors text-sm">
                Upload a PDF
              </button>
            </Link>
            <Link href="/chat">
              <button className="border-2 border-[#1d7689] text-[#1d7689] hover:bg-[#1d7689] hover:text-white font-semibold px-5 py-2.5 rounded-lg transition-colors text-sm">
                Start Chatting
              </button>
            </Link>
          </div>
        </div>

        {/* How it works */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-8">
          <h2 className="text-sm font-bold uppercase tracking-widest text-[#1d7689] mb-4">
            How it works
          </h2>
          <ol className="space-y-4">
            {[
              "Upload one or more PDF documents on the Upload page.",
              "The system extracts text, chunks it, and stores vector embeddings in PostgreSQL.",
              "Ask a question in the Chat page — the system retrieves relevant chunks and generates a grounded answer.",
            ].map((step, i) => (
              <li key={i} className="flex gap-4 items-start">
                <span className="flex-shrink-0 w-7 h-7 rounded-full bg-[#1d7689] text-white text-sm font-bold flex items-center justify-center">
                  {i + 1}
                </span>
                <p className="text-gray-600 pt-0.5">{step}</p>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
}
