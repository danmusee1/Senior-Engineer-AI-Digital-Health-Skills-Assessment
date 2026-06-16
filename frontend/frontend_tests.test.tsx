/**
 * Tests for UploadPage and ChatPage components.
 *
 * Setup required (if not already present):
 *   npm install --save-dev @testing-library/react @testing-library/jest-dom @testing-library/user-event jest jest-environment-jsdom
 *
 * Add to package.json:
 *   "jest": { "testEnvironment": "jsdom", "setupFilesAfterFramework": ["@testing-library/jest-dom"] }
 *
 * Run: npx jest
 */

import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";

// ─── Mocks ────────────────────────────────────────────────────────────────────

// Mock Next.js Link
jest.mock("next/link", () => {
  return function MockLink({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) {
    return <a href={href}>{children}</a>;
  };
});

// Mock environment variables
process.env.NEXT_PUBLIC_API_URL = "http://localhost:6100";
process.env.NEXT_PUBLIC_API_KEY = "test-secret";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const mockDocumentItem = (overrides = {}) => ({
  id: 1,
  filename: "test.pdf",
  content_type: "application/pdf",
  file_size_bytes: 1024 * 512, // 512 KB
  status: "completed" as const,
  chunk_count: 5,
  error_message: null,
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
  ...overrides,
});

const mockFetch = (responses: Array<{ ok: boolean; json: object; status?: number }>) => {
  let callIndex = 0;
  return jest.fn().mockImplementation(() => {
    const response = responses[callIndex] ?? responses[responses.length - 1];
    callIndex++;
    return Promise.resolve({
      ok: response.ok,
      status: response.status ?? (response.ok ? 200 : 400),
      json: () => Promise.resolve(response.json),
    });
  });
};

// ─── Upload Page Tests ─────────────────────────────────────────────────────────

// Lazy import so env vars are set first
let UploadPage: React.ComponentType;
beforeAll(async () => {
  const mod = await import("./src/app/upload/page");
  UploadPage = mod.default;
});

describe("UploadPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  // ── Rendering ──────────────────────────────────────────────────────────────

  describe("rendering", () => {
    it("renders the page heading and description", async () => {
      global.fetch = mockFetch([{ ok: true, json: { items: [], total: 0, limit: 20, offset: 0 } }]);
      render(<UploadPage />);
      expect(screen.getByText("Upload PDF")).toBeInTheDocument();
      expect(screen.getByText(/upload a pdf to ingest/i)).toBeInTheDocument();
    });

    it("renders the drag-and-drop zone", async () => {
      global.fetch = mockFetch([{ ok: true, json: { items: [], total: 0, limit: 20, offset: 0 } }]);
      render(<UploadPage />);
      expect(screen.getByText(/click or drag a pdf here/i)).toBeInTheDocument();
      expect(screen.getByText(/max 20mb/i)).toBeInTheDocument();
    });

    it("renders nav links to Upload and Chat", async () => {
      global.fetch = mockFetch([{ ok: true, json: { items: [], total: 0, limit: 20, offset: 0 } }]);
      render(<UploadPage />);
      expect(screen.getByRole("link", { name: /upload/i })).toHaveAttribute("href", "/upload");
      expect(screen.getByRole("link", { name: /chat/i })).toHaveAttribute("href", "/chat");
    });

    it("shows empty state when no documents exist", async () => {
      global.fetch = mockFetch([{ ok: true, json: { items: [], total: 0, limit: 20, offset: 0 } }]);
      render(<UploadPage />);
      await waitFor(() => {
        expect(screen.getByText(/no documents ingested yet/i)).toBeInTheDocument();
      });
    });

    it("lists documents returned from the API", async () => {
      const doc = mockDocumentItem({ filename: "report.pdf" });
      global.fetch = mockFetch([{ ok: true, json: { items: [doc], total: 1, limit: 20, offset: 0 } }]);
      render(<UploadPage />);
      await waitFor(() => {
        expect(screen.getByText("report.pdf")).toBeInTheDocument();
      });
    });

    it("displays document status badge", async () => {
      const doc = mockDocumentItem({ status: "processing" });
      global.fetch = mockFetch([{ ok: true, json: { items: [doc], total: 1, limit: 20, offset: 0 } }]);
      render(<UploadPage />);
      await waitFor(() => {
        expect(screen.getByText("processing")).toBeInTheDocument();
      });
    });

    it("displays chunk count for completed documents", async () => {
      const doc = mockDocumentItem({ status: "completed", chunk_count: 12 });
      global.fetch = mockFetch([{ ok: true, json: { items: [doc], total: 1, limit: 20, offset: 0 } }]);
      render(<UploadPage />);
      await waitFor(() => {
        expect(screen.getByText(/12 chunks/i)).toBeInTheDocument();
      });
    });

    it("displays error message for failed documents", async () => {
      const doc = mockDocumentItem({ status: "failed", error_message: "OCR failed" });
      global.fetch = mockFetch([{ ok: true, json: { items: [doc], total: 1, limit: 20, offset: 0 } }]);
      render(<UploadPage />);
      await waitFor(() => {
        expect(screen.getByText(/OCR failed/i)).toBeInTheDocument();
      });
    });
  });

  // ── File Upload ────────────────────────────────────────────────────────────

  describe("file upload", () => {
    it("shows success message after successful upload", async () => {
      const doc = mockDocumentItem({ filename: "my-doc.pdf" });
      global.fetch = mockFetch([
        { ok: true, json: { items: [], total: 0, limit: 20, offset: 0 } }, // initial fetch
        { ok: true, json: { document: doc, is_duplicate: false } },           // upload
        { ok: true, json: { items: [doc], total: 1, limit: 20, offset: 0 } }, // refetch
      ]);

      render(<UploadPage />);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = new File(["content"], "my-doc.pdf", { type: "application/pdf" });

      await act(async () => {
        fireEvent.change(input, { target: { files: [file] } });
      });

      await waitFor(() => {
        expect(screen.getByText(/uploaded.*processing/i)).toBeInTheDocument();
      });
    });

    it("shows duplicate message when file was already uploaded", async () => {
      const doc = mockDocumentItem({ filename: "existing.pdf" });
      global.fetch = mockFetch([
        { ok: true, json: { items: [], total: 0, limit: 20, offset: 0 } },
        { ok: true, json: { document: doc, is_duplicate: true } },
        { ok: true, json: { items: [doc], total: 1, limit: 20, offset: 0 } },
      ]);

      render(<UploadPage />);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = new File(["content"], "existing.pdf", { type: "application/pdf" });

      await act(async () => {
        fireEvent.change(input, { target: { files: [file] } });
      });

      await waitFor(() => {
        expect(screen.getByText(/already uploaded previously/i)).toBeInTheDocument();
      });
    });

    it("rejects non-PDF files with an error message", async () => {
      global.fetch = mockFetch([{ ok: true, json: { items: [], total: 0, limit: 20, offset: 0 } }]);
      render(<UploadPage />);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = new File(["content"], "doc.txt", { type: "text/plain" });

      await act(async () => {
        fireEvent.change(input, { target: { files: [file] } });
      });

      expect(screen.getByText(/only pdf files are accepted/i)).toBeInTheDocument();
      // fetch should not have been called for upload
      expect(global.fetch).toHaveBeenCalledTimes(1); // only initial documents fetch
    });

    it("rejects files larger than 20MB", async () => {
      global.fetch = mockFetch([{ ok: true, json: { items: [], total: 0, limit: 20, offset: 0 } }]);
      render(<UploadPage />);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;

      // Create a file object with a large size
      const largeFile = new File(["x".repeat(1024)], "large.pdf", { type: "application/pdf" });
      Object.defineProperty(largeFile, "size", { value: 21 * 1024 * 1024 });

      await act(async () => {
        fireEvent.change(input, { target: { files: [largeFile] } });
      });

      expect(screen.getByText(/file too large/i)).toBeInTheDocument();
    });

    it("shows loading message while upload is in progress", async () => {
      global.fetch = jest.fn().mockImplementation((url: string) => {
        if (url.includes("/rag/documents") && !url.includes("upload")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve({ items: [], total: 0, limit: 20, offset: 0 }) });
        }
        // Upload hangs
        return new Promise(() => {});
      });

      render(<UploadPage />);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = new File(["content"], "test.pdf", { type: "application/pdf" });

      act(() => {
        fireEvent.change(input, { target: { files: [file] } });
      });

      await waitFor(() => {
        expect(screen.getByText(/uploading/i)).toBeInTheDocument();
      });
    });

    it("shows error message when upload API returns an error", async () => {
      global.fetch = mockFetch([
        { ok: true, json: { items: [], total: 0, limit: 20, offset: 0 } },
        { ok: false, status: 422, json: { detail: "File does not appear to be a valid PDF." } },
      ]);

      render(<UploadPage />);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = new File(["content"], "fake.pdf", { type: "application/pdf" });

      await act(async () => {
        fireEvent.change(input, { target: { files: [file] } });
      });

      await waitFor(() => {
        expect(screen.getByText(/file does not appear to be a valid pdf/i)).toBeInTheDocument();
      });
    });

    it("shows error message on network failure", async () => {
      global.fetch = jest.fn()
        .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ items: [], total: 0, limit: 20, offset: 0 }) })
        .mockRejectedValueOnce(new Error("Network error"));

      render(<UploadPage />);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = new File(["content"], "test.pdf", { type: "application/pdf" });

      await act(async () => {
        fireEvent.change(input, { target: { files: [file] } });
      });

      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument();
      });
    });
  });

  // ── Drag and Drop ──────────────────────────────────────────────────────────

  describe("drag and drop", () => {
    it("highlights drop zone on drag over", async () => {
      global.fetch = mockFetch([{ ok: true, json: { items: [], total: 0, limit: 20, offset: 0 } }]);
      render(<UploadPage />);
     const dropZone = screen.getByText(/click or drag a pdf here/i)
  .closest("[class*='border-dashed']")!;

      fireEvent.dragOver(dropZone, { preventDefault: () => {} });
      expect(dropZone.className).toContain("border-[#1d7689]");
    });

    it("removes highlight on drag leave", async () => {
      global.fetch = mockFetch([{ ok: true, json: { items: [], total: 0, limit: 20, offset: 0 } }]);
      render(<UploadPage />);
      const dropZone = screen.getByText(/click or drag a pdf here/i)
  .closest("[class*='border-dashed']")!;

      fireEvent.dragOver(dropZone, { preventDefault: () => {} });
      fireEvent.dragLeave(dropZone);
      expect(dropZone).not.toHaveClass(/bg-\[#1d7689\]\/5/);
    });

    it("uploads file on drop", async () => {
      const doc = mockDocumentItem({ filename: "dropped.pdf" });
      global.fetch = mockFetch([
        { ok: true, json: { items: [], total: 0, limit: 20, offset: 0 } },
        { ok: true, json: { document: doc, is_duplicate: false } },
        { ok: true, json: { items: [doc], total: 1, limit: 20, offset: 0 } },
      ]);

      render(<UploadPage />);
      const dropZone = screen.getByText(/click or drag a pdf here/i)
  .closest("[class*='border-dashed']")!;
      const file = new File(["content"], "dropped.pdf", { type: "application/pdf" });

      await act(async () => {
        fireEvent.drop(dropZone, {
          preventDefault: () => {},
          dataTransfer: { files: [file] },
        });
      });

      await waitFor(() => {
        expect(screen.getByText(/uploaded.*processing/i)).toBeInTheDocument();
      });
    });
  });

  // ── Polling ────────────────────────────────────────────────────────────────

  describe("polling", () => {
    it("polls while a document is pending/processing", async () => {
      const pendingDoc = mockDocumentItem({ status: "pending" });
      const completedDoc = mockDocumentItem({ status: "completed" });

      global.fetch = jest.fn()
        .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ items: [pendingDoc], total: 1, limit: 20, offset: 0 }) })
        .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ items: [completedDoc], total: 1, limit: 20, offset: 0 }) });

      render(<UploadPage />);

      await waitFor(() => expect(screen.getByText("pending")).toBeInTheDocument());

      act(() => jest.advanceTimersByTime(3000));

      await waitFor(() => expect(screen.getByText("completed")).toBeInTheDocument());
    });
  });
});

// ─── Chat Page Tests ───────────────────────────────────────────────────────────

let ChatPage: React.ComponentType;
beforeAll(async () => {
  const mod = await import("./src/app/chat/page");
  ChatPage = mod.default;
});

describe("ChatPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ── Rendering ──────────────────────────────────────────────────────────────

  describe("rendering", () => {
    it("renders the chat heading and description", () => {
      render(<ChatPage />);
      expect(screen.getByText("Chat")).toBeInTheDocument();
      expect(screen.getByText(/ask questions grounded in your uploaded pdfs/i)).toBeInTheDocument();
    });

    it("renders the message input and send button", () => {
      render(<ChatPage />);
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
    });

    it("shows empty state prompt before any messages", () => {
      render(<ChatPage />);
      expect(screen.getByText(/upload a pdf then ask a question/i)).toBeInTheDocument();
    });

    it("renders nav links to Upload and Chat", () => {
      render(<ChatPage />);
      expect(screen.getByRole("link", { name: /upload/i })).toHaveAttribute("href", "/upload");
      expect(screen.getByRole("link", { name: /chat/i })).toHaveAttribute("href", "/chat");
    });

    it("send button is enabled initially", () => {
      render(<ChatPage />);
      expect(screen.getByRole("button", { name: /send/i })).not.toBeDisabled();
    });
  });

  // ── Sending Messages ───────────────────────────────────────────────────────

  describe("sending messages", () => {
    it("displays user message in the chat after sending", async () => {
      global.fetch = mockFetch([
        { ok: true, json: { answer: "Nairobi is the capital.", sources: [] } },
      ]);

      render(<ChatPage />);
      const input = screen.getByPlaceholderText(/ask a question/i);

      await userEvent.type(input, "What is the capital of Kenya?");
      await userEvent.click(screen.getByRole("button", { name: /send/i }));

      expect(screen.getByText("What is the capital of Kenya?")).toBeInTheDocument();
    });

    it("displays assistant answer after API responds", async () => {
      global.fetch = mockFetch([
        { ok: true, json: { answer: "Nairobi is the capital.", sources: [] } },
      ]);

      render(<ChatPage />);
      const input = screen.getByPlaceholderText(/ask a question/i);

      await userEvent.type(input, "What is the capital of Kenya?");
      await userEvent.click(screen.getByRole("button", { name: /send/i }));

      await waitFor(() => {
        expect(screen.getByText("Nairobi is the capital.")).toBeInTheDocument();
      });
    });

    it("clears input after sending", async () => {
      global.fetch = mockFetch([
        { ok: true, json: { answer: "Some answer.", sources: [] } },
      ]);

      render(<ChatPage />);
      const input = screen.getByPlaceholderText(/ask a question/i) as HTMLInputElement;

      await userEvent.type(input, "Hello");
      await userEvent.click(screen.getByRole("button", { name: /send/i }));

      expect(input.value).toBe("");
    });

    it("sends message on Enter key press", async () => {
      global.fetch = mockFetch([
        { ok: true, json: { answer: "Sure!", sources: [] } },
      ]);

      render(<ChatPage />);
      const input = screen.getByPlaceholderText(/ask a question/i);

      await userEvent.type(input, "Hello{Enter}");

      await waitFor(() => {
        expect(screen.getByText("Sure!")).toBeInTheDocument();
      });
    });

    it("does not send empty messages", async () => {
      global.fetch = jest.fn();
      render(<ChatPage />);

      await userEvent.click(screen.getByRole("button", { name: /send/i }));

      expect(global.fetch).not.toHaveBeenCalled();
    });

    it("does not send whitespace-only messages", async () => {
      global.fetch = jest.fn();
      render(<ChatPage />);
      const input = screen.getByPlaceholderText(/ask a question/i);

      await userEvent.type(input, "   ");
      await userEvent.click(screen.getByRole("button", { name: /send/i }));

      expect(global.fetch).not.toHaveBeenCalled();
    });

    it("shows thinking indicator while waiting for response", async () => {
      global.fetch = jest.fn().mockImplementation(() => new Promise(() => {})); // never resolves

      render(<ChatPage />);
      const input = screen.getByPlaceholderText(/ask a question/i);

      act(() => {
        fireEvent.change(input, { target: { value: "Hello?" } });
        fireEvent.click(screen.getByRole("button", { name: /send/i }));
      });

      await waitFor(() => {
        expect(screen.getByText(/thinking/i)).toBeInTheDocument();
      });
    });

    it("disables input and button while loading", async () => {
      global.fetch = jest.fn().mockImplementation(() => new Promise(() => {}));

      render(<ChatPage />);
      const input = screen.getByPlaceholderText(/ask a question/i);

      act(() => {
        fireEvent.change(input, { target: { value: "Hello?" } });
        fireEvent.click(screen.getByRole("button", { name: /send/i }));
      });

      await waitFor(() => {
        expect(input).toBeDisabled();
        expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
      });
    });
  });

  // ── Sources ────────────────────────────────────────────────────────────────

  describe("sources display", () => {
    it("displays source references when returned by the API", async () => {
      const sources = [
        {
          document_id: 1,
          filename: "report.pdf",
          chunk_index: 2,
          content: "Kenya's capital city is Nairobi, established in 1899.",
          similarity: 0.95,
        },
      ];

      global.fetch = mockFetch([
        { ok: true, json: { answer: "Nairobi is the capital.", sources } },
      ]);

      render(<ChatPage />);
      const input = screen.getByPlaceholderText(/ask a question/i);

      await userEvent.type(input, "Capital?");
      await userEvent.click(screen.getByRole("button", { name: /send/i }));

      await waitFor(() => {
        expect(screen.getByText(/sources/i)).toBeInTheDocument();
        expect(screen.getByText(/report\.pdf/i)).toBeInTheDocument();
        expect(screen.getByText(/95%/i)).toBeInTheDocument();
      });
    });

    it("does not show sources section when sources array is empty", async () => {
      global.fetch = mockFetch([
        { ok: true, json: { answer: "I don't know.", sources: [] } },
      ]);

      render(<ChatPage />);
      const input = screen.getByPlaceholderText(/ask a question/i);

      await userEvent.type(input, "Question?");
      await userEvent.click(screen.getByRole("button", { name: /send/i }));

      await waitFor(() => {
        expect(screen.getByText("I don't know.")).toBeInTheDocument();
        expect(screen.queryByText(/sources/i)).not.toBeInTheDocument();
      });
    });
  });

  // ── Error Handling ─────────────────────────────────────────────────────────

  describe("error handling", () => {
    it("shows error message when API returns an error", async () => {
      global.fetch = mockFetch([
        { ok: false, status: 500, json: { detail: "Query failed: embedding service down" } },
      ]);

      render(<ChatPage />);
      const input = screen.getByPlaceholderText(/ask a question/i);

      await userEvent.type(input, "Hello");
      await userEvent.click(screen.getByRole("button", { name: /send/i }));

      await waitFor(() => {
        expect(screen.getByText(/error.*query failed/i)).toBeInTheDocument();
      });
    });

    it("shows error message on network failure", async () => {
      global.fetch = jest.fn().mockRejectedValue(new Error("Failed to fetch"));

      render(<ChatPage />);
      const input = screen.getByPlaceholderText(/ask a question/i);

      await userEvent.type(input, "Hello");
      await userEvent.click(screen.getByRole("button", { name: /send/i }));

      await waitFor(() => {
        expect(screen.getByText(/error.*failed to fetch/i)).toBeInTheDocument();
      });
    });

    it("re-enables input after an error", async () => {
      global.fetch = jest.fn().mockRejectedValue(new Error("Network error"));

      render(<ChatPage />);
      const input = screen.getByPlaceholderText(/ask a question/i);

      await userEvent.type(input, "Hello");
      await userEvent.click(screen.getByRole("button", { name: /send/i }));

      await waitFor(() => {
        expect(input).not.toBeDisabled();
        expect(screen.getByRole("button", { name: /send/i })).not.toBeDisabled();
      });
    });
  });

  // ── Multi-turn ─────────────────────────────────────────────────────────────

  describe("multi-turn conversation", () => {
    it("accumulates multiple messages in the chat", async () => {
      global.fetch = jest.fn()
        .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ answer: "Answer 1.", sources: [] }) })
        .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ answer: "Answer 2.", sources: [] }) });

      render(<ChatPage />);
      const input = screen.getByPlaceholderText(/ask a question/i);

      await userEvent.type(input, "Question 1");
      await userEvent.click(screen.getByRole("button", { name: /send/i }));
      await waitFor(() => expect(screen.getByText("Answer 1.")).toBeInTheDocument());

      await userEvent.type(input, "Question 2");
      await userEvent.click(screen.getByRole("button", { name: /send/i }));
      await waitFor(() => expect(screen.getByText("Answer 2.")).toBeInTheDocument());

      expect(screen.getByText("Question 1")).toBeInTheDocument();
      expect(screen.getByText("Question 2")).toBeInTheDocument();
    });

    it("cannot send a second message while first is loading", async () => {
      global.fetch = jest.fn().mockImplementation(() => new Promise(() => {}));

      render(<ChatPage />);
      const input = screen.getByPlaceholderText(/ask a question/i);

      act(() => {
        fireEvent.change(input, { target: { value: "First question" } });
        fireEvent.click(screen.getByRole("button", { name: /send/i }));
      });

      await waitFor(() => expect(screen.getByRole("button", { name: /send/i })).toBeDisabled());

      // Trying to fire click again should do nothing
      fireEvent.click(screen.getByRole("button", { name: /send/i }));
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });
  });
});