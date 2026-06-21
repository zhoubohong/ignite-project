"use client";

import { useState, useRef, useEffect, useCallback } from "react";

interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  metadata?: {
    intent?: string;
    subject?: string;
    agent?: string;
  };
}

interface Stats {
  total_sessions: number;
  total_questions_answered: number;
  mastery_distribution: Record<string, number>;
  recent_mistakes: number;
  weak_points_top5: Array<{
    knowledge_point: string;
    p_learned: number;
    subject: string;
  }>;
}

interface MasteryItem {
  knowledge_point: string;
  subject: string;
  state: string;
  p_learned: number;
  total_attempts: number;
  correct_count: number;
}

interface DailyItem {
  date: string;
  total: number;
  correct: number;
  accuracy: number;
}

const SUBJECTS = [
  { value: "", label: "自动识别" },
  { value: "math", label: "数学" },
  { value: "physics", label: "物理" },
  { value: "chemistry", label: "化学" },
  { value: "biology", label: "生物" },
  { value: "chinese", label: "语文" },
  { value: "english", label: "英语" },
  { value: "history", label: "历史" },
  { value: "politics", label: "政治" },
];

const STATE_LABELS: Record<string, string> = {
  untouched: "未接触",
  exposed: "已了解",
  practicing: "练习中",
  mastered: "已掌握",
};

const ERROR_LABELS: Record<string, string> = {
  concept: "概念未掌握",
  formula: "公式套错",
  calculation: "计算粗心",
  unit: "单位遗漏",
  reading: "审题偏差",
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [userId] = useState(() => crypto.randomUUID());
  const [showDashboard, setShowDashboard] = useState(false);
  const [dashboardTab, setDashboardTab] = useState<"stats" | "mastery" | "mistakes" | "daily">("stats");
  const [stats, setStats] = useState<Stats | null>(null);
  const [mastery, setMastery] = useState<MasteryItem[] | null>(null);
  const [mistakes, setMistakes] = useState<Record<string, number> | null>(null);
  const [daily, setDaily] = useState<DailyItem[] | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [error, setError] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (showDashboard) {
      setDashboardLoading(true);
      Promise.all([
        fetch(`/api/dashboard/stats/${userId}`).then((r) => r.json()),
        fetch(`/api/dashboard/mastery/${userId}`).then((r) => r.json()),
        fetch(`/api/dashboard/mistakes/${userId}`).then((r) => r.json()),
        fetch(`/api/dashboard/daily/${userId}`).then((r) => r.json()),
      ])
        .then(([s, m, mi, d]) => {
          setStats(s);
          setMastery(m);
          setMistakes(mi);
          setDaily(d);
        })
        .catch(() => {})
        .finally(() => setDashboardLoading(false));
    }
  }, [showDashboard, userId]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setError("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);

    try {
      const resp = await fetch("/api/chat/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          session_id: sessionId,
          user_id: userId,
        }),
      });
      if (!resp.ok) throw new Error(`Server error: ${resp.status}`);
      const data = await resp.json();
      setSessionId(data.session_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.reply,
          metadata: {
            intent: data.intent,
            subject: data.subject,
            agent: data.agent,
          },
        },
      ]);
    } catch (e: any) {
      setError(e.message || "连接失败，请确认后端已启动");
    } finally {
      setLoading(false);
    }
  }, [input, loading, sessionId, userId]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const newSession = () => {
    setMessages([]);
    setSessionId(null);
    inputRef.current?.focus();
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Main Chat */}
      <div className="flex-1 flex flex-col max-w-3xl mx-auto w-full">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-3 border-b bg-white shrink-0">
          <h1 className="text-lg font-bold text-gray-800">
            伴学系统
            <span className="ml-2 text-sm font-normal text-gray-400">
              AI智能学习伴侣
            </span>
          </h1>
          <div className="flex gap-2">
            <button
              onClick={() => setShowDashboard(!showDashboard)}
              className="px-3 py-1.5 text-sm rounded-lg border hover:bg-gray-50"
            >
              {showDashboard ? "关闭面板" : "学习面板"}
            </button>
            <button
              onClick={newSession}
              className="px-3 py-1.5 text-sm rounded-lg bg-blue-500 text-white hover:bg-blue-600"
            >
              新会话
            </button>
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <p className="text-3xl mb-2">🎓</p>
              <p className="text-lg font-medium">你好！我是你的AI学习伴侣</p>
              <p className="text-sm mt-1">
                可以问我数学题、物理概念、英语单词、历史事件等任何学习问题
              </p>
              <div className="mt-6 flex flex-wrap gap-2 justify-center">
                {[
                  "解一道一元二次方程",
                  "光合作用的原理",
                  "英语完形填空技巧",
                  "辛亥革命的原因",
                ].map((q) => (
                  <button
                    key={q}
                    onClick={() => setInput(q)}
                    className="px-3 py-1.5 text-sm border rounded-full hover:bg-gray-100"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${
                msg.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                  msg.role === "user"
                    ? "bg-blue-500 text-white"
                    : "bg-white border shadow-sm"
                }`}
              >
                {msg.metadata && (
                  <div className="text-xs opacity-60 mb-1">
                    {msg.metadata.subject &&
                      SUBJECTS.find((s) => s.value === msg.metadata!.subject)?.label}
                    {" · "}
                    {msg.metadata.intent === "learn"
                      ? "讲解"
                      : msg.metadata.intent === "practice"
                      ? "练习"
                      : msg.metadata.intent}
                  </div>
                )}
                <div className="text-sm whitespace-pre-wrap leading-relaxed">
                  {msg.content}
                </div>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-white border shadow-sm rounded-2xl px-4 py-3">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                  <span
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: "0.1s" }}
                  />
                  <span
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: "0.2s" }}
                  />
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="flex justify-center">
              <div className="bg-red-50 text-red-600 px-4 py-2 rounded-lg text-sm">
                ⚠️ {error}
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t bg-white px-6 py-4 shrink-0">
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入你的学习问题..."
              disabled={loading}
              className="flex-1 px-4 py-2.5 border rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:opacity-50"
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              className="px-6 py-2.5 bg-blue-500 text-white rounded-xl hover:bg-blue-600 disabled:opacity-50 font-medium"
            >
              发送
            </button>
          </div>
        </div>
      </div>

      {/* Dashboard Sidebar */}
      {showDashboard && (
        <aside className="w-80 border-l bg-white overflow-y-auto shrink-0 flex flex-col">
          {/* Tab bar */}
          <div className="flex border-b shrink-0">
            {([
              ["stats", "概览"],
              ["mastery", "掌握度"],
              ["mistakes", "错题"],
              ["daily", "趋势"],
            ] as const).map(([tab, label]) => (
              <button
                key={tab}
                onClick={() => setDashboardTab(tab)}
                className={`flex-1 py-2 text-xs font-medium border-b-2 transition-colors ${
                  dashboardTab === tab
                    ? "border-blue-500 text-blue-600"
                    : "border-transparent text-gray-400 hover:text-gray-600"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="p-4 space-y-4 flex-1">
            {dashboardLoading && (
              <div className="flex justify-center py-8">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" />
                  <span className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }} />
                  <span className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }} />
                </div>
              </div>
            )}

            {!dashboardLoading && (
              <>
                {/* ── Stats Overview Tab ── */}
                {dashboardTab === "stats" && stats && (
                  <>
                    <h2 className="font-bold text-gray-700">📊 学习概览（近7天）</h2>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="bg-blue-50 rounded-lg p-3">
                        <p className="text-xs text-gray-500">学习会话</p>
                        <p className="text-xl font-bold text-blue-600">{stats.total_sessions}</p>
                      </div>
                      <div className="bg-green-50 rounded-lg p-3">
                        <p className="text-xs text-gray-500">做题总数</p>
                        <p className="text-xl font-bold text-green-600">{stats.total_questions_answered}</p>
                      </div>
                      <div className="bg-orange-50 rounded-lg p-3 col-span-2">
                        <p className="text-xs text-gray-500">近期错题</p>
                        <p className="text-xl font-bold text-orange-600">{stats.recent_mistakes}</p>
                      </div>
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-gray-600 mb-2">掌握度分布</h3>
                      <div className="space-y-1">
                        {Object.entries(stats.mastery_distribution).map(([k, v]) => (
                          <div key={k} className="flex justify-between text-sm">
                            <span>{STATE_LABELS[k] || k}</span>
                            <span className="font-medium">{v} 个</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    {stats.weak_points_top5.length > 0 && (
                      <div>
                        <h3 className="text-sm font-semibold text-red-600 mb-2">⚠️ 薄弱知识点 TOP5</h3>
                        <ul className="space-y-1 text-sm">
                          {stats.weak_points_top5.map((wp, i) => (
                            <li key={i} className="flex justify-between">
                              <span className="text-gray-700">[{wp.subject}] {wp.knowledge_point}</span>
                              <span className="text-red-500 font-medium">{Math.round(wp.p_learned * 100)}%</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </>
                )}

                {/* ── Mastery Detail Tab ── */}
                {dashboardTab === "mastery" && mastery && (
                  <>
                    <h2 className="font-bold text-gray-700">📋 掌握度详情</h2>
                    {mastery.length === 0 ? (
                      <p className="text-sm text-gray-400 text-center py-4">暂无数据，开始做题吧！</p>
                    ) : (
                      <ul className="space-y-2">
                        {mastery.map((m, i) => (
                          <li key={i} className="bg-gray-50 rounded-lg p-3">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-sm font-medium text-gray-700 truncate max-w-[140px]">
                                {m.knowledge_point}
                              </span>
                              <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                                m.state === "mastered" ? "bg-green-100 text-green-700" :
                                m.state === "practicing" ? "bg-blue-100 text-blue-700" :
                                m.state === "exposed" ? "bg-yellow-100 text-yellow-700" :
                                "bg-gray-100 text-gray-500"
                              }`}>
                                {STATE_LABELS[m.state] || m.state}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-xs text-gray-400">
                                {SUBJECTS.find((s) => s.value === m.subject)?.label || m.subject}
                              </span>
                              <span className="text-xs text-gray-400">
                                {m.correct_count}/{m.total_attempts} 次
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full transition-all ${
                                    m.p_learned >= 0.95 ? "bg-green-500" :
                                    m.p_learned >= 0.7 ? "bg-blue-500" :
                                    m.p_learned >= 0.4 ? "bg-yellow-500" :
                                    "bg-red-400"
                                  }`}
                                  style={{ width: `${Math.round(m.p_learned * 100)}%` }}
                                />
                              </div>
                              <span className="text-xs font-medium text-gray-500 w-10 text-right">
                                {Math.round(m.p_learned * 100)}%
                              </span>
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </>
                )}

                {/* ── Mistake Distribution Tab ── */}
                {dashboardTab === "mistakes" && mistakes && (
                  <>
                    <h2 className="font-bold text-gray-700">📉 错题分布（近30天）</h2>
                    {Object.keys(mistakes).length === 0 ? (
                      <p className="text-sm text-gray-400 text-center py-4">暂无错题，继续保持！</p>
                    ) : (
                      <div className="space-y-2">
                        {Object.entries(mistakes)
                          .sort(([, a], [, b]) => b - a)
                          .map(([errType, count]) => {
                            const total = Object.values(mistakes).reduce((s, v) => s + v, 0);
                            const pct = Math.round((count / total) * 100);
                            return (
                              <div key={errType}>
                                <div className="flex justify-between text-xs mb-0.5">
                                  <span className="text-gray-600">
                                    {ERROR_LABELS[errType] || errType}
                                  </span>
                                  <span className="text-gray-400">
                                    {count} 次 · {pct}%
                                  </span>
                                </div>
                                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                                  <div
                                    className={`h-full rounded-full transition-all ${
                                      errType === "concept" ? "bg-red-500" :
                                      errType === "formula" ? "bg-orange-500" :
                                      errType === "calculation" ? "bg-yellow-500" :
                                      errType === "unit" ? "bg-blue-400" :
                                      "bg-purple-400"
                                    }`}
                                    style={{ width: `${Math.max(pct, 4)}%` }}
                                  />
                                </div>
                              </div>
                            );
                          })}
                      </div>
                    )}
                  </>
                )}

                {/* ── Daily Activity Tab ── */}
                {dashboardTab === "daily" && daily && (
                  <>
                    <h2 className="font-bold text-gray-700">📈 每日答题趋势（近7天）</h2>
                    {daily.length === 0 ? (
                      <p className="text-sm text-gray-400 text-center py-4">暂无数据</p>
                    ) : (
                      <div className="space-y-3">
                        {/* Summary row */}
                        <div className="flex justify-between text-xs text-gray-400">
                          <span>日期</span>
                          <span>题数 / 正确率</span>
                        </div>
                        {daily.map((d) => (
                          <div key={d.date} className="flex items-center gap-2">
                            <span className="text-xs text-gray-500 w-12 shrink-0">
                              {d.date.slice(5)}
                            </span>
                            <div className="flex-1 flex items-center gap-1">
                              {/* Bar: total questions */}
                              <div className="flex-1 h-5 bg-gray-100 rounded relative overflow-hidden">
                                <div
                                  className="absolute inset-y-0 left-0 bg-blue-200 rounded"
                                  style={{ width: `${Math.min((d.total / Math.max(...daily.map((x) => x.total), 1)) * 100, 100)}%` }}
                                />
                                <span className="absolute inset-0 flex items-center pl-1 text-xs text-gray-600 font-medium">
                                  {d.total}题
                                </span>
                              </div>
                              {/* Accuracy indicator */}
                              <span
                                className={`text-xs font-medium w-11 text-right ${
                                  d.accuracy >= 80 ? "text-green-600" :
                                  d.accuracy >= 60 ? "text-yellow-600" :
                                  d.accuracy > 0 ? "text-red-500" :
                                  "text-gray-300"
                                }`}
                              >
                                {d.accuracy > 0 ? `${d.accuracy}%` : "—"}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </>
            )}
          </div>
        </aside>
      )}
    </div>
  );
}
