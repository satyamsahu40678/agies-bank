"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { api, dateTime, useResource } from "@/lib/api";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  Modal,
  Notice,
  PageHeader,
} from "@/components/ui";

type Document = {
  id: string;
  title: string;
  kind: string;
  filename: string;
  chunk_count: number;
  created_at: string;
};
type Citation = {
  document_id: string;
  title: string;
  excerpt: string;
  page: number | null;
};
type Answer = {
  answer: string;
  citations: Citation[];
  agent: string;
  trace_id: string;
};

const suggestions = [
  "What are the eligibility requirements?",
  "Summarize the important terms and exclusions.",
  "What fees or charges should I know about?",
];

export default function DocumentsPage() {
  const { data, loading, error, refresh } =
    useResource<Document[]>("/documents");
  const [selectedId, setSelectedId] = useState<string>("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [asking, setAsking] = useState(false);
  const [queryError, setQueryError] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [notice, setNotice] = useState("");
  const [sourceOpen, setSourceOpen] = useState(false);
  const [sourceLoading, setSourceLoading] = useState(false);
  const [sourceError, setSourceError] = useState("");
  const [source, setSource] = useState<{
    document: Document;
    pages: { page: number; text: string }[];
  } | null>(null);
  const titleRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const selected = data?.find((document) => document.id === selectedId);

  useEffect(() => {
    if (!selectedId && data?.length) setSelectedId(data[0].id);
  }, [data, selectedId]);

  async function previewSource() {
    if (!selectedId) return;
    setSourceOpen(true);
    setSourceLoading(true);
    setSourceError("");
    setSource(null);
    try {
      setSource(
        await api<{
          document: Document;
          pages: { page: number; text: string }[];
        }>(`/documents/${selectedId}/content`),
      );
    } catch (cause) {
      setSourceError(
        cause instanceof Error
          ? cause.message
          : "Source passages could not be loaded.",
      );
    } finally {
      setSourceLoading(false);
    }
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setUploadError("Choose a document to upload.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setUploadError("Documents must be 5 MB or smaller.");
      return;
    }
    const form = new FormData();
    form.append("file", file);
    const title = titleRef.current?.value.trim();
    if (title) form.append("title", title);
    setUploading(true);
    setUploadError("");
    try {
      const document = await api<Document>("/documents", {
        method: "POST",
        body: form,
      });
      await refresh();
      setSelectedId(document.id);
      setAnswer(null);
      setQuestion("");
      setUploadOpen(false);
      setNotice(
        `“${document.title}” is ready. Ask a question to explore its source material.`,
      );
    } catch (cause) {
      setUploadError(
        cause instanceof Error
          ? cause.message
          : "The document could not be uploaded.",
      );
    } finally {
      setUploading(false);
    }
  }

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim() || !selectedId || asking) return;
    setAsking(true);
    setQueryError("");
    setAnswer(null);
    try {
      setAnswer(
        await api<Answer>("/documents/query", {
          method: "POST",
          body: { question: question.trim(), document_id: selectedId },
        }),
      );
    } catch (cause) {
      setQueryError(
        cause instanceof Error
          ? cause.message
          : "Your question could not be answered.",
      );
    } finally {
      setAsking(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="DOCUMENT INTELLIGENCE"
        title="Clarity, with a source."
        description="Understand your statements and policy documents. Every answer is grounded in the document you select."
        action={
          <Button
            disabled={asking}
            onClick={() => {
              setUploadError("");
              setUploadOpen(true);
            }}
          >
            Upload document
          </Button>
        }
      />
      {notice && <Notice tone="success">{notice}</Notice>}
      <div style={{ height: 20 }} />
      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={refresh} />
      ) : !data?.length ? (
        <EmptyState
          title="Your document library is ready"
          description="Upload a PDF, text file, Markdown, or CSV document to ask questions about its contents."
        />
      ) : (
        <div
          className="grid two documents-layout"
          style={{ alignItems: "start" }}
        >
          <Card>
            <div className="row-between">
              <h2 className="section-title">Your library</h2>
              <span className="chip">{data.length} documents</span>
            </div>
            <p className="muted" style={{ fontSize: 13, marginBottom: 20 }}>
              Your documents and shared bank policies.
            </p>
            <div className="stack">
              {data.map((document) => (
                <button
                  key={document.id}
                  type="button"
                  disabled={asking}
                  aria-pressed={selectedId === document.id}
                  onClick={() => {
                    setSelectedId(document.id);
                    setAnswer(null);
                    setQueryError("");
                    setQuestion("");
                  }}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    border: `1px solid ${selectedId === document.id ? "#079b78" : "var(--border, #e3e8eb)"}`,
                    background:
                      selectedId === document.id ? "#edf8f4" : "transparent",
                    color: "inherit",
                    borderRadius: 12,
                    padding: 16,
                    cursor: asking ? "wait" : "pointer",
                  }}
                >
                  <span className="row-between" style={{ gap: 8 }}>
                    <strong style={{ lineHeight: 1.45 }}>
                      {document.title}
                    </strong>
                    <span
                      aria-hidden="true"
                      style={{ color: "#04866a", fontSize: 20 }}
                    >
                      ↗
                    </span>
                  </span>
                  <span
                    className="muted"
                    style={{
                      display: "block",
                      fontSize: 12,
                      marginTop: 7,
                      overflowWrap: "anywhere",
                    }}
                  >
                    {document.filename}
                  </span>
                  <span
                    className="muted"
                    style={{ display: "block", fontSize: 11, marginTop: 10 }}
                  >
                    {document.chunk_count} indexed passages ·{" "}
                    {document.kind.replace(/_/g, " ")}
                  </span>
                </button>
              ))}
            </div>
          </Card>
          <div className="stack">
            <Card>
              <span
                className="chip"
                style={{ background: "#edf8f4", color: "#04785f" }}
              >
                DOCUMENT AGENT
              </span>
              <div className="row-between">
                <h2 style={{ margin: "18px 0 8px", fontSize: 24 }}>
                  {selected?.title}
                </h2>
                <Button
                  variant="ghost"
                  onClick={previewSource}
                  disabled={!selectedId}
                >
                  View source
                </Button>
              </div>
              <p className="muted" style={{ fontSize: 13, marginBottom: 24 }}>
                Added {selected ? dateTime(selected.created_at) : ""} · Answers
                search this document only.
              </p>
              <form onSubmit={ask} className="stack">
                <Field
                  label="Ask about this document"
                  hint="Answers include source excerpts for you to verify."
                >
                  <textarea
                    aria-label="Ask about this document"
                    className="textarea"
                    rows={3}
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    placeholder="For example: what are the repayment terms?"
                    required
                    maxLength={2000}
                    disabled={asking}
                  />
                </Field>
                <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
                  {suggestions.map((suggestion) => (
                    <button
                      type="button"
                      key={suggestion}
                      className="chip"
                      disabled={asking}
                      onClick={() => setQuestion(suggestion)}
                      style={{
                        cursor: "pointer",
                        textAlign: "left",
                        whiteSpace: "normal",
                        border: "1px solid var(--border, #e3e8eb)",
                        fontSize: 11,
                      }}
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
                <div>
                  <Button
                    disabled={!question.trim() || asking || !selectedId}
                    type="submit"
                  >
                    {asking ? "Searching document…" : "Ask document"}
                    <span aria-hidden="true"> ↗</span>
                  </Button>
                </div>
              </form>
              {queryError && (
                <div style={{ marginTop: 18 }}>
                  <Notice tone="danger">{queryError}</Notice>
                </div>
              )}
            </Card>
            {asking && (
              <Card>
                <LoadingState />
              </Card>
            )}
            {answer && (
              <Card>
                <div className="row-between">
                  <h2 className="section-title">Your answer</h2>
                  <span className="chip">
                    {answer.agent.replace(/_/g, " ")}
                  </span>
                </div>
                <p
                  style={{
                    whiteSpace: "pre-wrap",
                    lineHeight: 1.8,
                    fontSize: 15,
                  }}
                >
                  {answer.answer}
                </p>
                <div className="divider" />
                <h3 style={{ fontSize: 13, marginBottom: 16 }}>
                  Source evidence{" "}
                  <span className="muted">({answer.citations.length})</span>
                </h3>
                <div className="stack">
                  {answer.citations.map((citation, index) => (
                    <blockquote
                      key={`${citation.document_id}-${index}`}
                      style={{
                        margin: 0,
                        borderLeft: "3px solid #0b9b79",
                        padding: "12px 16px",
                        background: "#f5f8f7",
                        borderRadius: "0 8px 8px 0",
                      }}
                    >
                      <div
                        style={{
                          fontSize: 12,
                          fontWeight: 700,
                          marginBottom: 8,
                        }}
                      >
                        [{index + 1}] {citation.title}
                        {citation.page ? ` · Page ${citation.page}` : ""}
                      </div>
                      <p
                        style={{
                          margin: 0,
                          fontSize: 13,
                          lineHeight: 1.75,
                          whiteSpace: "pre-wrap",
                        }}
                      >
                        {citation.excerpt}
                      </p>
                    </blockquote>
                  ))}
                </div>
                {!answer.citations.length && (
                  <Notice tone="warning">
                    No matching source evidence was found. Try a more specific
                    question, and verify the original document before making a
                    decision.
                  </Notice>
                )}
                <p
                  className="muted"
                  style={{
                    marginTop: 20,
                    fontSize: 11,
                    overflowWrap: "anywhere",
                  }}
                >
                  Trace {answer.trace_id}
                </p>
              </Card>
            )}
            {!answer && !asking && (
              <div
                style={{
                  padding: "18px 20px",
                  display: "flex",
                  gap: 14,
                  alignItems: "flex-start",
                }}
              >
                <span
                  aria-hidden="true"
                  style={{ fontSize: 23, color: "#07886a" }}
                >
                  ◎
                </span>
                <div>
                  <strong style={{ fontSize: 13 }}>
                    Grounded in your documents
                  </strong>
                  <p
                    className="muted"
                    style={{ fontSize: 13, lineHeight: 1.7, margin: "5px 0" }}
                  >
                    Answers use indexed text and cite exact source excerpts.
                    They help you understand a document and do not replace
                    professional financial advice.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      {sourceOpen && (
        <Modal
          title={source?.document.title || "Indexed source passages"}
          onClose={() => setSourceOpen(false)}
        >
          {sourceLoading ? (
            <LoadingState />
          ) : sourceError ? (
            <Notice tone="danger">{sourceError}</Notice>
          ) : (
            <div className="stack">
              <p className="muted">
                Exact indexed passages from your selected document. Long pages
                may have overlapping passages.
              </p>
              {source?.pages.map((passage, index) => (
                <div
                  key={index}
                  style={{
                    borderLeft: "3px solid #82a275",
                    padding: "12px 16px",
                    background: "#f6f8f2",
                    borderRadius: 8,
                  }}
                >
                  <strong style={{ fontSize: 12 }}>
                    Page {passage.page} · Passage {index + 1}
                  </strong>
                  <p
                    style={{
                      whiteSpace: "pre-wrap",
                      fontSize: 13,
                      lineHeight: 1.8,
                    }}
                  >
                    {passage.text}
                  </p>
                </div>
              ))}
            </div>
          )}
        </Modal>
      )}
      {uploadOpen && (
        <Modal
          title="Upload a document"
          onClose={() => {
            if (!uploading) setUploadOpen(false);
          }}
        >
          <form onSubmit={upload} className="stack">
            <p className="muted" style={{ lineHeight: 1.7 }}>
              Add a policy, statement, or financial document to your private
              library. Text is extracted and indexed for source-based answers.
            </p>
            <Field
              label="Document title"
              hint="Optional. If empty, the file name is used."
            >
              <input
                aria-label="Document title"
                className="input"
                ref={titleRef}
                maxLength={150}
                placeholder="e.g. Home loan terms"
                disabled={uploading}
              />
            </Field>
            <Field
              label="Document file"
              hint="PDF, plain text, Markdown, or CSV · maximum 5 MB"
            >
              <input
                aria-label="Document file"
                ref={fileRef}
                className="input"
                type="file"
                accept=".pdf,.txt,.md,.csv,application/pdf,text/plain,text/markdown,text/csv"
                required
                disabled={uploading}
              />
            </Field>
            <Notice>
              Use text-based PDFs. Scanned PDFs without searchable text may need
              OCR before uploading.
            </Notice>
            {uploadError && <Notice tone="danger">{uploadError}</Notice>}
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setUploadOpen(false)}
                disabled={uploading}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={uploading}>
                {uploading ? "Indexing document…" : "Upload and index"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
      <style jsx>{`
        .documents-layout {
          grid-template-columns: minmax(240px, 0.72fr) minmax(0, 1.65fr);
        }
        @media (max-width: 1050px) {
          .documents-layout {
            grid-template-columns: minmax(0, 1fr);
          }
        }
      `}</style>
    </>
  );
}
