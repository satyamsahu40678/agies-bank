"use client";

import { useEffect, useRef, useState } from "react";
import { BookOpen, ExternalLink, Search } from "lucide-react";
import { useResource } from "@/lib/api";
import { ChatMarkdown } from "@/components/chat-markdown";
import { AskAiButton } from "@/components/ai-help";
import { Card, ErrorState, LoadingState, Notice, PageHeader } from "@/components/ui";
import styles from "@/components/ai-workspace.module.css";

type Guide = { id: string; title: string; category: string; publisher: string; source_url: string; summary: string; content: string; reviewed_at: string; jurisdiction: string; notice: string; questions: string[] };

export default function KnowledgePage() {
  const resource = useResource<Guide[]>("/knowledge");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState("");
  const reading = useRef<HTMLDivElement>(null);
  useEffect(() => { if (selected) reading.current?.scrollIntoView({ behavior: "smooth", block: "start" }); }, [selected]);
  if (resource.loading && !resource.data) return <LoadingState />;
  if (!resource.data) return <ErrorState message={resource.error || "Unable to load banking guides."} onRetry={resource.refresh} />;
  const guides = resource.data.filter(g => `${g.title} ${g.category} ${g.content}`.toLowerCase().includes(query.toLowerCase()));
  const active = resource.data.find(g => g.id === selected);
  return <>
    <PageHeader eyebrow="BANKING, EXPLAINED" title="Learn from trusted banking sources" description="Plain-language guides grounded in RBI, DICGC, NPCI and Government of India publications. Read the source, then ask your banking guide." />
    <Notice>{resource.data[0]?.notice}</Notice>
    <label className={styles.search}><Search size={18} /><input aria-label="Search banking guides" placeholder="Search deposits, payments, KYC, complaints…" value={query} onChange={e => setQuery(e.target.value)} /></label>
    <div className={styles.guideGrid}>{guides.map(guide => <Card key={guide.id} className={styles.guide}>
      <div className="row-between"><BookOpen size={23} /><span className="chip">{guide.category}</span></div>
      <h2>{guide.title}</h2><p>{guide.summary}</p><small>{guide.publisher} · India · reviewed {guide.reviewed_at}</small>
      <div className={styles.guideActions}><button className="button button-secondary" onClick={() => setSelected(guide.id)}>Read guide</button><AskAiButton prompt={guide.questions[0]}>Explain with AI</AskAiButton></div>
      <a href={guide.source_url} target="_blank" rel="noopener noreferrer">Official source <ExternalLink size={13} /></a>
    </Card>)}</div>
    {!guides.length && <Notice>No guide matches that search. Try UPI, insurance, KYC or complaints.</Notice>}
    {active && <div ref={reading} style={{ scrollMarginTop: 100 }}><Card className={styles.section}><div className={styles.heading}><h2>{active.title}</h2><button className="button button-ghost" onClick={() => setSelected("")}>Close guide</button></div><ChatMarkdown>{active.content}</ChatMarkdown><p className="muted">Educational summary · {active.publisher} · reviewed {active.reviewed_at}</p><a href={active.source_url} target="_blank" rel="noopener noreferrer">Read the official publication ↗</a><div className={styles.guideActions}>{active.questions.map(question => <AskAiButton key={question} prompt={question}>{question}</AskAiButton>)}</div></Card></div>}
  </>;
}
