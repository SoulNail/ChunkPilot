import { useEffect, useState } from "react";
import { api } from "../api";

export default function Search() {
  const [cols, setCols] = useState<string[]>([]);
  const [collection, setCollection] = useState("");
  const [query, setQuery] = useState("");
  const [rerank, setRerank] = useState(true);
  const [results, setResults] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.collections().then((c) => { setCols(c); if (c[0]) setCollection(c[0]); });
  }, []);

  const run = async () => {
    if (!query.trim()) return;
    setBusy(true); setErr("");
    try { setResults(await api.search({ collection, query, limit: 5, rerank })); }
    catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  };

  return (
    <div className="space-y-4">
      <div className="bg-white p-4 rounded-lg space-y-3">
        <div className="flex gap-2">
          <select className="border border-slate-300 rounded-md px-3 py-2 text-sm"
            value={collection} onChange={(e) => setCollection(e.target.value)}>
            {cols.map((c) => <option key={c}>{c}</option>)}
          </select>
          <input className="flex-1 border border-slate-300 rounded-md px-3 py-2 text-sm"
            placeholder="输入检索内容…" value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()} />
          <button onClick={run} disabled={busy}
            className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm disabled:opacity-50">
            {busy ? "检索中…" : "检索"}
          </button>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={rerank} onChange={(e) => setRerank(e.target.checked)} />
          重排序（混合召回后用 reranker 精排）
        </label>
      </div>

      {err && <div className="text-red-600 text-sm">{err}</div>}

      <div className="space-y-3">
        {results.map((r, i) => (
          <div key={i} className="bg-white p-4 rounded-lg">
            <div className="flex justify-between text-xs text-slate-500 mb-1">
              <span>#{i + 1} · {r.source}</span>
              <span>score {r.score?.toFixed(4)}</span>
            </div>
            <div className="text-sm whitespace-pre-wrap text-slate-700">{r.text.slice(0, 500)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
