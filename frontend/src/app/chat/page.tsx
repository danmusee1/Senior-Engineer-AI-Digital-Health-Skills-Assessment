"use client";
import { useState, useRef, useEffect } from "react";
import Link from "next/link";

const apiUrl = process.env.NEXT_PUBLIC_API_URL;
const API = apiUrl;

interface Source { content: string; similarity: number; }
interface Message { role: "user" | "assistant"; content: string; sources?: Source[]; }

export default function ChatPage() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const sendMessage = async () => {
        if (!input.trim() || loading) return;
        const query = input.trim();
        setInput("");
        setMessages((prev) => [...prev, { role: "user", content: query }]);
        setLoading(true);
        try {
            const res = await fetch(`${API}/rag/query`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Query failed.");
            setMessages((prev) => [...prev, { role: "assistant", content: data.answer, sources: data.sources }]);
        } catch (e: any) {
            setMessages((prev) => [...prev, { role: "assistant", content: `Error: ${e.message}` }]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 flex flex-col">
            <nav className="bg-[#193946] px-8 h-14 flex items-center gap-8 shadow">
                <Link href="/" className="text-white font-bold text-lg mr-auto tracking-tight">
                    Last Mile Health RAG
                </Link>
                <Link href="/upload" className="text-white/80 hover:text-white font-medium text-sm transition-colors">
                    Upload
                </Link>
                <Link href="/chat" className="text-white font-medium text-sm border-b-2 border-white pb-0.5">
                    Chat
                </Link>
            </nav>

            <div className="max-w-3xl mx-auto px-6 py-10 w-full flex-1 flex flex-col">
                <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-8 flex flex-col flex-1">
                    <h1 className="text-2xl font-bold text-[#193946] mb-1">Chat</h1>
                    <p className="text-gray-500 mb-6 text-sm">Ask questions grounded in your uploaded PDFs.</p>

                    {/* Messages */}
                    <div className="flex-1 overflow-y-auto bg-gray-50 rounded-xl border border-gray-100 p-4 mb-4 flex flex-col gap-3 min-h-[400px] max-h-[500px]">
                        {messages.length === 0 && (
                            <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
                                Upload a PDF then ask a question.
                            </div>
                        )}
                        {messages.map((msg, i) => (
                            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                                <div className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed
                  ${msg.role === "user"
                                        ? "bg-[#1d7689] text-white rounded-br-sm"
                                        : "bg-white border border-gray-200 text-gray-800 rounded-bl-sm shadow-sm"
                                    }`}>
                                    {msg.content}
                                    {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
                                        <div className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-400 space-y-1">
                                            <p className="font-semibold text-gray-500">Sources:</p>
                                            {msg.sources.slice(0, 3).map((s, j) => (
                                                <p key={j}>
                                                    [{j + 1}] {(s.similarity * 100).toFixed(0)}% — {s.content.slice(0, 100)}...
                                                </p>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                        {loading && (
                            <div className="flex justify-start">
                                <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 text-sm text-gray-400 shadow-sm">
                                    <span className="animate-pulse">Thinking...</span>
                                </div>
                            </div>
                        )}
                        <div ref={bottomRef} />
                    </div>

                    {/* Input */}
                    <div className="flex gap-3">
                        <input
                            type="text"
                            className="flex-1 border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#1d7689] transition-colors"
                            placeholder="Ask a question about your documents..."
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                            disabled={loading}
                        />
                        <button
                            onClick={sendMessage}
                            disabled={loading}
                            className="bg-[#1d7689] hover:bg-[#193946] disabled:bg-gray-300 text-white font-semibold px-5 py-2.5 rounded-lg transition-colors text-sm"
                        >
                            Send
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
