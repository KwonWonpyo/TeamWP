"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

// ─── 타입 ───────────────────────────────────────────────────────────────────

type Project = {
  project_id: string;
  name: string;
  repo_url: string;
  repos: string[];
  default_branch: string;
  tech_stack: string;
};

type Task = {
  task_id: string;
  project_id: string;
  title: string;
  description: string;
  source: string;
  status: "pending" | "in_progress" | "done" | "failed";
  created_at: string;
  issue_number?: number | null;
};

type Conversation = {
  message_id: string;
  task_id: string;
  agent_role: string;
  content: string;
  timestamp: string;
  token_usage: number;
};

type TaskFeedPayload = {
  task: Task;
  conversations: Conversation[];
};

// ─── 환경 변수 ───────────────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:3000";
const WS_BASE = process.env.NEXT_PUBLIC_WS_BASE ?? "ws://127.0.0.1:3000";
const API_KEY = process.env.NEXT_PUBLIC_ARCHITECTURE_API_KEY ?? "";

// ─── 유틸리티 ────────────────────────────────────────────────────────────────

function toLocalTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return iso;
  }
}

function authHeaders(): Record<string, string> {
  return API_KEY ? { "x-api-key": API_KEY } : {};
}

// ─── 에이전트 역할 설정 ───────────────────────────────────────────────────────

const ROLE_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  vice:        { label: "바이스 (PM)",      color: "text-blue-300",   bg: "bg-blue-900/40" },
  pm:          { label: "바이스 (PM)",      color: "text-blue-300",   bg: "bg-blue-900/40" },
  azure:       { label: "아주르 (UI)",      color: "text-purple-300", bg: "bg-purple-900/40" },
  fleur:       { label: "플뢰르 (Dev)",     color: "text-emerald-300",bg: "bg-emerald-900/40" },
  developer:   { label: "플뢰르 (Dev)",     color: "text-emerald-300",bg: "bg-emerald-900/40" },
  elsi:        { label: "엘시 (Advocate)", color: "text-amber-300",  bg: "bg-amber-900/40" },
  bethel:      { label: "베델 (QA)",        color: "text-cyan-300",   bg: "bg-cyan-900/40" },
  qa:          { label: "베델 (QA)",        color: "text-cyan-300",   bg: "bg-cyan-900/40" },
  orchestrator:{ label: "오케스트레이터",    color: "text-slate-400",  bg: "bg-slate-800/60" },
};

function getRoleConfig(role: string) {
  return ROLE_CONFIG[role.toLowerCase()] ?? { label: role, color: "text-slate-300", bg: "bg-slate-800/60" };
}

// ─── 상태 뱃지 ────────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: Task["status"] }) {
  const map = {
    pending:    "bg-slate-700 text-slate-300",
    in_progress:"bg-yellow-800/60 text-yellow-300 animate-pulse",
    done:       "bg-emerald-800/60 text-emerald-300",
    failed:     "bg-red-800/60 text-red-300",
  };
  const labels = { pending: "대기", in_progress: "진행 중", done: "완료", failed: "실패" };
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${map[status] ?? map.pending}`}>
      {labels[status] ?? status}
    </span>
  );
}

// ─── 에이전트 파이프라인 표시 ──────────────────────────────────────────────────

const PIPELINE_STEPS = [
  { role: "vice",  label: "바이스" },
  { role: "azure", label: "아주르" },
  { role: "fleur", label: "플뢰르" },
  { role: "elsi",  label: "엘시" },
  { role: "bethel",label: "베델" },
];

function AgentPipeline({ conversations }: { conversations: Conversation[] }) {
  const spokenRoles = new Set(conversations.map((c) => c.agent_role.toLowerCase()));
  return (
    <div className="flex items-center gap-1 text-xs">
      {PIPELINE_STEPS.map((step, i) => {
        const active = spokenRoles.has(step.role);
        const cfg = getRoleConfig(step.role);
        return (
          <div key={step.role} className="flex items-center gap-1">
            <span className={`rounded px-2 py-0.5 font-medium ${active ? cfg.bg + " " + cfg.color : "bg-slate-800 text-slate-600"}`}>
              {step.label}
            </span>
            {i < PIPELINE_STEPS.length - 1 && (
              <span className="text-slate-700">→</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── 메인 컴포넌트 ────────────────────────────────────────────────────────────

export default function Home() {
  // 상태
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [taskFeed, setTaskFeed] = useState<TaskFeedPayload | null>(null);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  // 프로젝트 등록 폼
  const [pForm, setPForm] = useState({ project_id: "", name: "", repo_url: "", tech_stack: "", default_branch: "main" });
  const [extraRepos, setExtraRepos] = useState<string[]>([]);

  // 지시 입력 폼
  const [instrForm, setInstrForm] = useState({ product_id: "", title: "", raw_text: "" });

  const feedBottomRef = useRef<HTMLDivElement>(null);

  // ─── API 호출 ────────────────────────────────────────────────────────────────

  const loadProjects = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/projects`);
      const data = await res.json();
      setProjects(data.projects ?? []);
    } catch {
      setStatus("프로젝트 목록 조회 실패");
    }
  }, []);

  const loadTasks = useCallback(async (projectId: string) => {
    if (!projectId) return;
    try {
      const res = await fetch(`${API_BASE}/api/projects/${projectId}/tasks`);
      const data = await res.json();
      setTasks(data.tasks ?? []);
    } catch {
      setStatus("태스크 목록 조회 실패");
    }
  }, []);

  // ─── 초기 로드 ───────────────────────────────────────────────────────────────

  useEffect(() => { void loadProjects(); }, [loadProjects]);

  useEffect(() => {
    void loadTasks(selectedProjectId);
  }, [selectedProjectId, loadTasks]);

  // ─── 진행 중 태스크 자동 폴링 ────────────────────────────────────────────────

  useEffect(() => {
    if (!selectedProjectId) return;
    const hasActive = tasks.some((t) => t.status === "pending" || t.status === "in_progress");
    if (!hasActive) return;
    const id = setInterval(() => { void loadTasks(selectedProjectId); }, 3000);
    return () => clearInterval(id);
  }, [tasks, selectedProjectId, loadTasks]);

  // ─── WebSocket 연결 ──────────────────────────────────────────────────────────

  useEffect(() => {
    if (!selectedTaskId) return;
    const wsUrl = API_KEY
      ? `${WS_BASE}/ws/tasks/${selectedTaskId}?api_key=${encodeURIComponent(API_KEY)}`
      : `${WS_BASE}/ws/tasks/${selectedTaskId}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (ev) => {
      const payload = JSON.parse(ev.data as string);
      if (payload.type === "task_feed") {
        setTaskFeed(payload.data as TaskFeedPayload);
        // 태스크 완료 시 목록 갱신
        const t = (payload.data as TaskFeedPayload).task;
        if (t.status === "done" || t.status === "failed") {
          void loadTasks(t.project_id);
        }
      } else if (payload.type === "error") {
        setStatus(`WS 오류: ${payload.detail as string}`);
      }
    };
    ws.onerror = () => setStatus("WS 연결 오류");

    return () => { ws.close(); };
  }, [selectedTaskId, loadTasks]);

  // ─── 피드 자동 스크롤 ────────────────────────────────────────────────────────

  useEffect(() => {
    feedBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [taskFeed?.conversations.length]);

  // ─── 이벤트 핸들러 ──────────────────────────────────────────────────────────

  async function handleCreateProject(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const repos = [pForm.repo_url, ...extraRepos.filter(Boolean)];
      const res = await fetch(`${API_BASE}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ ...pForm, repos }),
      });
      if (!res.ok) { setStatus("프로젝트 저장 실패"); return; }
      setStatus(`프로젝트 "${pForm.name}" 저장 완료`);
      setPForm({ project_id: "", name: "", repo_url: "", tech_stack: "", default_branch: "main" });
      setExtraRepos([]);
      await loadProjects();
      setSelectedProjectId(pForm.project_id);
      setInstrForm((f) => ({ ...f, product_id: pForm.project_id }));
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmitInstruction(e: FormEvent) {
    e.preventDefault();
    if (!instrForm.product_id) { setStatus("제품을 선택하세요"); return; }
    if (!instrForm.raw_text.trim()) { setStatus("지시 내용을 입력하세요"); return; }
    setLoading(true);
    setStatus("지시 제출 중...");
    try {
      const res = await fetch(`${API_BASE}/api/instructions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          product_id: instrForm.product_id,
          raw_text: instrForm.raw_text,
          title: instrForm.title || undefined,
        }),
      });
      if (!res.ok) {
        const err = (await res.json()) as { detail?: string };
        setStatus(`지시 제출 실패: ${err.detail ?? res.statusText}`);
        return;
      }
      const data = await res.json() as { task_id: string };
      setStatus(`지시 수신 완료 — 에이전트 팀 작업 시작 (task: ${data.task_id})`);
      setInstrForm((f) => ({ ...f, title: "", raw_text: "" }));
      setSelectedTaskId(data.task_id);
      setTaskFeed(null);
      await loadTasks(instrForm.product_id);
    } finally {
      setLoading(false);
    }
  }

  // ─── 렌더링 ──────────────────────────────────────────────────────────────────

  const selectedProject = projects.find((p) => p.project_id === selectedProjectId);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">

      {/* 헤더 */}
      <header className="border-b border-slate-800 bg-slate-900 px-6 py-3">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div>
            <h1 className="text-base font-bold tracking-wide">TeamWP Dashboard</h1>
            <p className="text-xs text-slate-500">AI 에이전트 팀 지시 센터</p>
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <span>{API_BASE}</span>
            {status && (
              <span className="max-w-xs truncate rounded bg-slate-800 px-2 py-1 text-cyan-400">
                {status}
              </span>
            )}
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-0 lg:grid-cols-12">

        {/* ── 왼쪽 패널 ── */}
        <aside className="space-y-4 border-r border-slate-800 p-5 lg:col-span-4">

          {/* 지시 입력 (메인) */}
          <section className="rounded-xl border border-slate-700 bg-slate-900 p-4">
            <h2 className="mb-3 text-sm font-bold text-slate-200">지시 입력</h2>
            <form onSubmit={handleSubmitInstruction} className="space-y-3">
              <div>
                <label className="mb-1 block text-xs text-slate-400">제품 선택</label>
                <select
                  className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-500"
                  value={instrForm.product_id}
                  onChange={(e) => setInstrForm((f) => ({ ...f, product_id: e.target.value }))}
                  required
                >
                  <option value="">제품을 선택하세요</option>
                  {projects.map((p) => (
                    <option key={p.project_id} value={p.project_id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs text-slate-400">제목 (선택)</label>
                <input
                  className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-500"
                  placeholder="비워두면 지시 내용에서 자동 추출"
                  value={instrForm.title}
                  onChange={(e) => setInstrForm((f) => ({ ...f, title: e.target.value }))}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-slate-400">지시 내용</label>
                <textarea
                  className="h-28 w-full resize-none rounded-lg bg-slate-800 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-500"
                  placeholder="에이전트 팀에게 지시할 내용을 자유롭게 입력하세요"
                  value={instrForm.raw_text}
                  onChange={(e) => setInstrForm((f) => ({ ...f, raw_text: e.target.value }))}
                  required
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-lg bg-cyan-600 py-2 text-sm font-semibold hover:bg-cyan-500 disabled:opacity-50"
              >
                {loading ? "처리 중..." : "팀에 지시하기"}
              </button>
            </form>
          </section>

          {/* 제품 등록 */}
          <section className="rounded-xl border border-slate-800 bg-slate-900 p-4">
            <h2 className="mb-3 text-sm font-bold text-slate-200">제품 등록</h2>
            <form onSubmit={handleCreateProject} className="space-y-2">
              <input
                className="w-full rounded bg-slate-800 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-slate-500"
                placeholder="project_id (영문 소문자, 하이픈)"
                value={pForm.project_id}
                onChange={(e) => setPForm((f) => ({ ...f, project_id: e.target.value }))}
                required
              />
              <input
                className="w-full rounded bg-slate-800 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-slate-500"
                placeholder="제품 이름"
                value={pForm.name}
                onChange={(e) => setPForm((f) => ({ ...f, name: e.target.value }))}
                required
              />
              <input
                className="w-full rounded bg-slate-800 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-slate-500"
                placeholder="대표 저장소 (owner/repo)"
                value={pForm.repo_url}
                onChange={(e) => setPForm((f) => ({ ...f, repo_url: e.target.value }))}
                required
              />
              {extraRepos.map((r, i) => (
                <div key={i} className="flex gap-1">
                  <input
                    className="flex-1 rounded bg-slate-800 px-3 py-1.5 text-sm focus:outline-none"
                    placeholder={`추가 저장소 ${i + 2}`}
                    value={r}
                    onChange={(e) => setExtraRepos((prev) => prev.map((x, j) => j === i ? e.target.value : x))}
                  />
                  <button
                    type="button"
                    onClick={() => setExtraRepos((prev) => prev.filter((_, j) => j !== i))}
                    className="rounded bg-slate-700 px-2 text-xs text-slate-400 hover:bg-slate-600"
                  >
                    ✕
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => setExtraRepos((prev) => [...prev, ""])}
                className="w-full rounded border border-dashed border-slate-700 py-1 text-xs text-slate-500 hover:border-slate-600 hover:text-slate-400"
              >
                + 저장소 추가
              </button>
              <input
                className="w-full rounded bg-slate-800 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-slate-500"
                placeholder="기술 스택 (예: Next.js, FastAPI)"
                value={pForm.tech_stack}
                onChange={(e) => setPForm((f) => ({ ...f, tech_stack: e.target.value }))}
              />
              <button
                type="submit"
                disabled={loading}
                className="w-full rounded bg-slate-700 py-1.5 text-sm font-semibold hover:bg-slate-600 disabled:opacity-50"
              >
                제품 저장
              </button>
            </form>
          </section>

          {/* 제품 목록 */}
          {projects.length > 0 && (
            <section className="rounded-xl border border-slate-800 bg-slate-900 p-4">
              <h2 className="mb-2 text-sm font-bold text-slate-200">등록된 제품</h2>
              <div className="space-y-1">
                {projects.map((p) => (
                  <button
                    key={p.project_id}
                    type="button"
                    onClick={() => {
                      setSelectedProjectId(p.project_id);
                      setInstrForm((f) => ({ ...f, product_id: p.project_id }));
                      setSelectedTaskId("");
                      setTaskFeed(null);
                    }}
                    className={`w-full rounded px-3 py-2 text-left text-sm ${
                      selectedProjectId === p.project_id
                        ? "bg-slate-700 text-slate-100"
                        : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                    }`}
                  >
                    <div className="font-medium">{p.name}</div>
                    <div className="text-xs opacity-60">{p.repo_url}</div>
                  </button>
                ))}
              </div>
            </section>
          )}
        </aside>

        {/* ── 오른쪽 패널 ── */}
        <div className="flex flex-col p-5 lg:col-span-8">

          {/* 작업 히스토리 */}
          <section className="mb-4">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-200">
                작업 히스토리{selectedProject && ` — ${selectedProject.name}`}
              </h2>
              {selectedProjectId && (
                <button
                  type="button"
                  onClick={() => void loadTasks(selectedProjectId)}
                  className="text-xs text-slate-500 hover:text-slate-300"
                >
                  새로고침
                </button>
              )}
            </div>

            {tasks.length === 0 ? (
              <div className="rounded-lg border border-slate-800 p-4 text-center text-sm text-slate-600">
                {selectedProjectId ? "아직 작업이 없습니다." : "왼쪽에서 제품을 선택하세요."}
              </div>
            ) : (
              <div className="grid gap-2">
                {tasks.map((task) => {
                  const selected = task.task_id === selectedTaskId;
                  return (
                    <button
                      key={task.task_id}
                      type="button"
                      onClick={() => {
                        setSelectedTaskId(task.task_id);
                        setTaskFeed(null);
                      }}
                      className={`rounded-lg border p-3 text-left transition-colors ${
                        selected
                          ? "border-cyan-600 bg-slate-800"
                          : "border-slate-800 bg-slate-900 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-sm font-medium">{task.title}</span>
                        <StatusBadge status={task.status} />
                      </div>
                      <div className="mt-1 flex items-center gap-3 text-xs text-slate-500">
                        <span className="rounded bg-slate-800 px-1.5">{task.source}</span>
                        {task.issue_number && <span>이슈 #{task.issue_number}</span>}
                        <span>{toLocalTime(task.created_at)}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </section>

          {/* 실시간 대화 피드 */}
          <section className="flex-1 rounded-xl border border-slate-800 bg-slate-900 p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-200">실시간 대화 피드</h2>
              {taskFeed && <AgentPipeline conversations={taskFeed.conversations} />}
            </div>

            {!taskFeed ? (
              <div className="flex h-40 items-center justify-center text-sm text-slate-600">
                {selectedTaskId ? "연결 중..." : "작업을 선택하면 실시간 로그가 표시됩니다."}
              </div>
            ) : (
              <>
                {/* 태스크 요약 */}
                <div className="mb-3 rounded-lg bg-slate-800/60 px-3 py-2 text-xs text-slate-400">
                  <span className="font-medium text-slate-300">{taskFeed.task.title}</span>
                  <span className="mx-2 text-slate-600">·</span>
                  <StatusBadge status={taskFeed.task.status} />
                  <span className="ml-2">{taskFeed.conversations.length}개 메시지</span>
                </div>

                {/* 대화 목록 */}
                <ul className="max-h-[520px] space-y-2 overflow-y-auto pr-1">
                  {taskFeed.conversations.map((msg) => {
                    const cfg = getRoleConfig(msg.agent_role);
                    return (
                      <li key={msg.message_id} className={`rounded-lg p-3 ${cfg.bg}`}>
                        <div className="mb-1 flex items-center justify-between">
                          <span className={`text-xs font-semibold ${cfg.color}`}>
                            {cfg.label}
                          </span>
                          <div className="flex items-center gap-2 text-xs text-slate-600">
                            {msg.token_usage > 0 && (
                              <span>{msg.token_usage.toLocaleString()} tokens</span>
                            )}
                            <span>{toLocalTime(msg.timestamp)}</span>
                          </div>
                        </div>
                        <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-200">
                          {msg.content}
                        </p>
                      </li>
                    );
                  })}
                  <div ref={feedBottomRef} />
                </ul>
              </>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
