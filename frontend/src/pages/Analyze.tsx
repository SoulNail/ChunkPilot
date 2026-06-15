import { useEffect, useState } from "react";
import { api, ingestStream, type Doc } from "../api";

const DEFAULTS = {
  chunk_size: 1000,
  chunk_overlap: 150,
  separators: null as string[] | null,
  prepend_heading_path: false,
  answer_prompt: "",
};

export default function Analyze() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [filename, setFilename] = useState("");
  const [form, setForm] = useState({ ...DEFAULTS });
  const [reasoning, setReasoning] = useState("");      // 仅 LLM 分析时有
  const [profile, setProfile] = useState<any>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [progress, setProgress] = useState<any>(null);

  const load = () => api.listDocs().then((d) => {
    setDocs(d);
    if (!filename && d[0]) selectDoc(d[0].name, d);
  });
  useEffect(() => { load(); }, []);

  // 选择文档时，把它已保存的参数填进表单（没有就用默认）
  const selectDoc = (name: string, list = docs) => {
    setFilename(name);
    setReasoning(""); setProfile(null); setProgress(null); setMsg("");
    const d = list.find((x) => x.name === name);
    const p = d?.params;
    setForm({
      chunk_size: p?.chunk_size ?? DEFAULTS.chunk_size,
      chunk_overlap: p?.chunk_overlap ?? DEFAULTS.chunk_overlap,
      separators: p?.separators ?? DEFAULTS.separators,
      prepend_heading_path: p?.prepend_heading_path ?? DEFAULTS.prepend_heading_path,
      answer_prompt: d?.analysis?.suggested_answer_prompt ?? DEFAULTS.answer_prompt,
    });
  };

  const set = (k: string, v: any) => setForm((f) => ({ ...f, [k]: v }));

  // 可选：让 LLM 分析，结果填入表单
  const analyze = async () => {
    setAnalyzing(true); setMsg("");
    try {
      const plan = await api.analyze(filename);
      setForm({
        chunk_size: plan.chunk_size ?? DEFAULTS.chunk_size,
        chunk_overlap: plan.chunk_overlap ?? DEFAULTS.chunk_overlap,
        separators: plan.separators ?? null,
        prepend_heading_path: !!plan.prepend_heading_path,
        answer_prompt: plan.suggested_answer_prompt ?? "",
      });
      setReasoning(plan.reasoning || "");
      setProfile(plan._profile || null);
    } catch (e: any) { setMsg(e.message); }
    finally { setAnalyzing(false); }
  };

  const paramsPayload = () => ({
    chunk_size: form.chunk_size,
    chunk_overlap: form.chunk_overlap,
    separators: form.separators,
    prepend_heading_path: form.prepend_heading_path,
  });

  const saveOnly = async () => {
    setSaving(true); setMsg("");
    try {
      await api.saveParams(filename, paramsPayload(), undefined, form.answer_prompt);
      await load();
      setMsg("参数已保存 ✅");
    } catch (e: any) { setMsg(e.message); }
    finally { setSaving(false); }
  };

  const ingest = async () => {
    setMsg(""); setProgress(null);
    try {
      // 先持久化参数（含回答风格），再灌库
      await api.saveParams(filename, paramsPayload(), undefined, form.answer_prompt);
      const { job_id } = await api.startIngest({ filename, params: paramsPayload() });
      ingestStream(job_id, setProgress, () => load());
    } catch (e: any) { setMsg(e.message); }
  };

  const pct = progress?.total ? Math.round((progress.done / progress.total) * 100) : 0;
  const cur = docs.find((d) => d.name === filename);

  return (
    <div className="space-y-4">
      <div className="flex gap-2 items-center bg-white p-4 rounded-lg">
        <select className="border border-slate-300 rounded-md px-3 py-2 text-sm flex-1"
          value={filename} onChange={(e) => selectDoc(e.target.value)}>
          {docs.map((d) => <option key={d.name}>{d.name}</option>)}
        </select>
        <button onClick={analyze} disabled={analyzing || !filename}
          className="px-4 py-2 bg-white border border-indigo-600 text-indigo-600 rounded-md text-sm disabled:opacity-50">
          {analyzing ? "分析中…" : "用 LLM 分析参数（可选）"}
        </button>
      </div>

      {msg && <div className={`text-sm ${msg.includes("✅") ? "text-emerald-600" : "text-red-600"}`}>{msg}</div>}

      {filename && (
        <div className="bg-white p-4 rounded-lg space-y-3">
          <div className="text-sm text-slate-500 flex justify-between">
            <span>
              {profile
                ? `画像：${profile.char_count} 字符 · ${profile.language} · ${profile.heading_count} 标题 · ${profile.code_fence_count} 代码块`
                : "直接手动填参数，或点上方让 LLM 给建议"}
            </span>
            <span className="text-slate-400">目标库：{cur?.collection}</span>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Num label="chunk_size 每块字符数" value={form.chunk_size} onChange={(v: number) => set("chunk_size", v)} />
            <Num label="chunk_overlap 块间重叠" value={form.chunk_overlap} onChange={(v: number) => set("chunk_overlap", v)} />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.prepend_heading_path}
              onChange={(e) => set("prepend_heading_path", e.target.checked)} />
            为每块前置标题路径作为上下文
          </label>
          <div>
            <span className="text-sm text-slate-600">separators（JSON 数组，留空 null 用默认递归切分）</span>
            <input className="mt-1 w-full border border-slate-300 rounded-md px-3 py-2 text-sm font-mono"
              value={form.separators === null ? "" : JSON.stringify(form.separators)}
              placeholder='例如 ["\n## ","\n### ","\n\n","\n"," "]'
              onChange={(e) => {
                const t = e.target.value.trim();
                if (t === "") return set("separators", null);
                try { set("separators", JSON.parse(t)); } catch { /* 暂不更新，等合法 JSON */ }
              }} />
          </div>

          {reasoning && (
            <div className="text-sm bg-amber-50 border border-amber-200 rounded-md p-3">
              <b>LLM 判断依据：</b>{reasoning}
            </div>
          )}

          <div>
            <span className="text-sm text-slate-600">回答风格 prompt（供 Agent 经 MCP 读取，可留空）</span>
            <textarea className="mt-1 w-full border border-slate-300 rounded-md px-3 py-2 text-sm h-20"
              value={form.answer_prompt}
              onChange={(e) => set("answer_prompt", e.target.value)} />
          </div>

          <div className="flex gap-2">
            <button onClick={saveOnly} disabled={saving}
              className="px-4 py-2 bg-white border border-slate-300 text-slate-700 rounded-md text-sm disabled:opacity-50">
              {saving ? "保存中…" : "仅保存参数"}
            </button>
            <button onClick={ingest}
              className="px-4 py-2 bg-emerald-600 text-white rounded-md text-sm">
              保存并按此参数灌库
            </button>
          </div>
        </div>
      )}

      {progress && (
        <div className="bg-white p-4 rounded-lg">
          <div className="flex justify-between text-sm mb-1">
            <span>灌库 · {progress.collection} · {progress.status}</span>
            <span>{progress.done}/{progress.total}</span>
          </div>
          <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
            <div className="h-full bg-emerald-500 transition-all" style={{ width: `${pct}%` }} />
          </div>
          {progress.status === "error" && <div className="text-red-600 text-sm mt-2">{progress.error}</div>}
          {progress.status === "done" && <div className="text-emerald-600 text-sm mt-2">完成 ✅</div>}
        </div>
      )}
    </div>
  );
}

function Num({ label, value, onChange }: any) {
  return (
    <label className="block">
      <span className="text-sm text-slate-600">{label}</span>
      <input type="number" className="mt-1 w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
        value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  );
}
