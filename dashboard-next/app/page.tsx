"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type Project = {
  project_id: string;
  name: string;
  repo_url: string;
  default_branch: string;
  tech_stack: string;
};

type Task = {
  task_id: string;
  project_id: string;
  title: string;
  description: string;
  source: string;
  status: string;
  created_at: string;
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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:3000";
const WS_BASE = process.env.NEXT_PUBLIC_WS_BASE ?? "ws://127.0.0.1:3000";
const API_KEY = process.env.NEXT_PUBLIC_ARCHITECTURE_API_KEY ?? "";

function toLocalTime(iso: string) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function authHeaders() {
  return API_KEY ? { "x-api-key": API_KEY } : {};
}

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string>("");
  const [taskFeed, setTaskFeed] = useState<TaskFeedPayload | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");

  const [projectForm, setProjectForm] = useState({
    project_id: "",
    name: "",
    repo_url: "",
    default_branch: "master",
    tech_stack: "",
  });
  const [taskForm, setTaskForm] = useState({
    title: "",
    description: "",
    source: "cli",
  });

  const selectedProject = useMemo(
    () => projects.find((p) => p.project_id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );

  useEffect(() => {
    const run = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/projects`);
        if (!res.ok) throw new Error("프로젝트 목록 조회 실패");
        const data = await res.json();
        setProjects(data.projects ?? []);
      } catch (e) {
        setStatusMessage(String(e));
      }
    };
    void run();
  }, []);

  useEffect(() => {
    const run = async () => {
      if (!selectedProjectId) return;
      try {
        const res = await fetch(`${API_BASE}/api/projects/${selectedProjectId}/tasks`);
        if (!res.ok) throw new Error("태스크 목록 조회 실패");
        const data = await res.json();
        setTasks(data.tasks ?? []);
      } catch (e) {
        setStatusMessage(String(e));
      }
    };
    void run();
  }, [selectedProjectId]);

  useEffect(() => {
    if (!selectedTaskId) return;

    const wsUrl = API_KEY
      ? `${WS_BASE}/ws/tasks/${selectedTaskId}?api_key=${encodeURIComponent(API_KEY)}`
      : `${WS_BASE}/ws/tasks/${selectedTaskId}`;
    const ws = new WebSocket(wsUrl);
    ws.onopen = () => setStatusMessage(`실시간 연결됨: ${selectedTaskId}`);

    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === "task_feed") {
        setTaskFeed(payload.data as TaskFeedPayload);
        setStatusMessage(`실시간 연결됨: ${selectedTaskId}`);
      } else if (payload.type === "error") {
        setStatusMessage(`WS 오류: ${payload.detail}`);
      }
    };
    ws.onerror = () => setStatusMessage("WS 연결 오류");
    ws.onclose = () => setStatusMessage("WS 연결 종료");

    return () => {
      ws.close();
    };
  }, [selectedTaskId]);

  async function handleCreateProject(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const res = await fetch(`${API_BASE}/api/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(projectForm),
    });
    if (!res.ok) {
      setStatusMessage("프로젝트 생성 실패");
      return;
    }
    setStatusMessage("프로젝트 저장 완료");
    const projectRes = await fetch(`${API_BASE}/api/projects`);
    if (projectRes.ok) {
      const projectData = await projectRes.json();
      setProjects(projectData.projects ?? []);
    }
    setSelectedProjectId(projectForm.project_id);
  }

  async function handleCreateTask(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedProjectId) {
      setStatusMessage("먼저 프로젝트를 선택하세요.");
      return;
    }
    const res = await fetch(`${API_BASE}/api/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        project_id: selectedProjectId,
        title: taskForm.title,
        description: taskForm.description,
        source: taskForm.source,
        auto_enqueue: true,
      }),
    });
    if (!res.ok) {
      setStatusMessage("태스크 생성 실패");
      return;
    }
    const data = await res.json();
    setStatusMessage(`태스크 생성 + 큐 적재 완료: ${data.task.task_id}`);
    const tasksRes = await fetch(`${API_BASE}/api/projects/${selectedProjectId}/tasks`);
    if (tasksRes.ok) {
      const tasksData = await tasksRes.json();
      setTasks(tasksData.tasks ?? []);
    }
    setSelectedTaskId(data.task.task_id);
    setTaskFeed(null);
  }

  async function runWorkerOnce() {
    const res = await fetch(`${API_BASE}/api/workers/run-once`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ timeout_seconds: 1 }),
    });
    if (!res.ok) {
      setStatusMessage("워커 실행 실패");
      return;
    }
    const data = await res.json();
    setStatusMessage(data.message);
    if (selectedProjectId) {
      const tasksRes = await fetch(`${API_BASE}/api/projects/${selectedProjectId}/tasks`);
      if (tasksRes.ok) {
        const tasksData = await tasksRes.json();
        setTasks(tasksData.tasks ?? []);
      }
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 p-6 text-slate-100">
      <div className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-12">
        <section className="space-y-4 rounded-xl border border-slate-800 bg-slate-900 p-4 lg:col-span-4">
          <h1 className="text-xl font-bold">Phase 3 Dashboard (Next.js)</h1>
          <p className="text-sm text-slate-400">
            FastAPI API + WebSocket 실시간 Conversation Feed
          </p>
          <div className="rounded bg-slate-800 p-3 text-xs text-slate-300">
            <div>API: {API_BASE}</div>
            <div>WS: {WS_BASE}</div>
          </div>
          <div className="rounded bg-slate-800 p-3 text-xs text-cyan-300">
            상태: {statusMessage || "대기 중"}
          </div>

          <form className="space-y-2 rounded border border-slate-700 p-3" onSubmit={handleCreateProject}>
            <h2 className="text-sm font-semibold">프로젝트 등록</h2>
            <input
              className="w-full rounded bg-slate-800 px-2 py-1 text-sm"
              placeholder="project_id"
              value={projectForm.project_id}
              onChange={(e) => setProjectForm((p) => ({ ...p, project_id: e.target.value }))}
              required
            />
            <input
              className="w-full rounded bg-slate-800 px-2 py-1 text-sm"
              placeholder="name"
              value={projectForm.name}
              onChange={(e) => setProjectForm((p) => ({ ...p, name: e.target.value }))}
              required
            />
            <input
              className="w-full rounded bg-slate-800 px-2 py-1 text-sm"
              placeholder="repo_url"
              value={projectForm.repo_url}
              onChange={(e) => setProjectForm((p) => ({ ...p, repo_url: e.target.value }))}
              required
            />
            <input
              className="w-full rounded bg-slate-800 px-2 py-1 text-sm"
              placeholder="tech_stack"
              value={projectForm.tech_stack}
              onChange={(e) => setProjectForm((p) => ({ ...p, tech_stack: e.target.value }))}
              required
            />
            <button className="w-full rounded bg-cyan-600 py-1 text-sm font-semibold hover:bg-cyan-500" type="submit">
              프로젝트 저장
            </button>
          </form>

          <div className="space-y-2 rounded border border-slate-700 p-3">
            <h2 className="text-sm font-semibold">프로젝트 선택</h2>
            <select
              className="w-full rounded bg-slate-800 px-2 py-1 text-sm"
              value={selectedProjectId}
              onChange={(e) => {
                setSelectedProjectId(e.target.value);
                setTasks([]);
                setSelectedTaskId("");
                setTaskFeed(null);
              }}
            >
              <option value="">선택하세요</option>
              {projects.map((project) => (
                <option key={project.project_id} value={project.project_id}>
                  {project.name} ({project.project_id})
                </option>
              ))}
            </select>
            {selectedProject && (
              <p className="text-xs text-slate-400">
                {selectedProject.repo_url}
              </p>
            )}
          </div>

          <form className="space-y-2 rounded border border-slate-700 p-3" onSubmit={handleCreateTask}>
            <h2 className="text-sm font-semibold">태스크 생성(+큐 적재)</h2>
            <input
              className="w-full rounded bg-slate-800 px-2 py-1 text-sm"
              placeholder="title"
              value={taskForm.title}
              onChange={(e) => setTaskForm((p) => ({ ...p, title: e.target.value }))}
              required
            />
            <textarea
              className="h-20 w-full rounded bg-slate-800 px-2 py-1 text-sm"
              placeholder="description"
              value={taskForm.description}
              onChange={(e) => setTaskForm((p) => ({ ...p, description: e.target.value }))}
              required
            />
            <button
              className="w-full rounded bg-emerald-600 py-1 text-sm font-semibold hover:bg-emerald-500"
              type="submit"
            >
              태스크 생성
            </button>
            <button
              className="w-full rounded bg-violet-600 py-1 text-sm font-semibold hover:bg-violet-500"
              type="button"
              onClick={runWorkerOnce}
            >
              워커 1회 실행
            </button>
          </form>
        </section>

        <section className="space-y-4 rounded-xl border border-slate-800 bg-slate-900 p-4 lg:col-span-8">
          <h2 className="text-lg font-semibold">Task Timeline</h2>
          <div className="grid gap-2">
            {tasks.length === 0 && (
              <div className="rounded border border-slate-800 bg-slate-800 p-3 text-sm text-slate-400">
                태스크가 없습니다.
              </div>
            )}
            {tasks.map((task) => {
              const selected = task.task_id === selectedTaskId;
              return (
                <button
                  key={task.task_id}
                  className={`rounded border p-3 text-left ${
                    selected
                      ? "border-cyan-400 bg-slate-800"
                      : "border-slate-800 bg-slate-900 hover:border-slate-600"
                  }`}
                  onClick={() => {
                    setSelectedTaskId(task.task_id);
                    setTaskFeed(null);
                  }}
                  type="button"
                >
                  <div className="text-sm font-semibold">{task.title}</div>
                  <div className="text-xs text-slate-400">{task.task_id}</div>
                  <div className="mt-1 flex items-center gap-3 text-xs">
                    <span className="rounded bg-slate-700 px-2 py-0.5">{task.status}</span>
                    <span className="text-slate-400">{toLocalTime(task.created_at)}</span>
                  </div>
                </button>
              );
            })}
          </div>

          <div className="rounded border border-slate-800 bg-slate-800 p-4">
            <h3 className="mb-2 text-sm font-semibold">Live Conversation Feed</h3>
            {!taskFeed && (
              <p className="text-sm text-slate-400">
                태스크를 선택하면 WebSocket으로 실시간 로그를 수신합니다.
              </p>
            )}
            {taskFeed && (
              <div className="space-y-2">
                <div className="rounded bg-slate-900 p-2 text-xs">
                  Task: {taskFeed.task.task_id} / Status: {taskFeed.task.status}
                </div>
                <ul className="max-h-[420px] space-y-2 overflow-auto">
                  {taskFeed.conversations.map((message) => (
                    <li key={message.message_id} className="rounded bg-slate-900 p-2">
                      <div className="flex items-center justify-between text-xs text-cyan-300">
                        <span>{message.agent_role}</span>
                        <span>{toLocalTime(message.timestamp)}</span>
                      </div>
                      <p className="mt-1 text-sm text-slate-200">{message.content}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
