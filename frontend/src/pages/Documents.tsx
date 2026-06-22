import { useEffect, useRef, useState } from "react";
import { api, type Doc } from "../api";

export default function Documents() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [uploading, setUploading] = useState(false);
  const [importing, setImporting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const kbRef = useRef<HTMLInputElement>(null);

  const load = () => api.listDocs().then(setDocs).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);

  const onUpload = async (f: File) => {
    setUploading(true); setErr("");
    try { await api.uploadDoc(f); await load(); }
    catch (e: any) { setErr(e.message); }
    finally { setUploading(false); }
  };

  const onDelete = async (name: string) => {
    if (!confirm(`删除 ${name}？`)) return;
    try { await api.deleteDoc(name); await load(); }
    catch (e: any) { setErr(e.message); }
  };

  const onImport = async (f: File) => {
    setImporting(true); setErr(""); setMsg("");
    try {
      const r = await api.importKb(f);
      setMsg(`已导入知识库 ${r.collection}（${r.points_count} 块${r.wrote_doc ? "，含原文档" : ""}）`);
      await load();
    } catch (e: any) { setErr(e.message); }
    finally { setImporting(false); if (kbRef.current) kbRef.current.value = ""; }
  };

  return (
    <div className="space-y-4">
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) onUpload(f); }}
        className="border-2 border-dashed border-slate-300 rounded-lg p-8 text-center bg-white"
      >
        <p className="text-slate-500 mb-2">拖拽文件到此，或</p>
        <button
          onClick={() => fileRef.current?.click()}
          className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm"
        >
          {uploading ? "上传中…" : "选择文件"}
        </button>
        <input ref={fileRef} type="file" hidden
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload(f); }} />
      </div>

      <div className="flex items-center gap-3 text-sm">
        <button
          onClick={() => kbRef.current?.click()}
          className="px-3 py-1.5 border border-indigo-300 text-indigo-700 rounded-md"
        >
          {importing ? "导入中…" : "导入知识库（.zip）"}
        </button>
        <span className="text-slate-400 text-xs">
          在 GPU 机上灌好后导出的 .kb.zip，可在此导入到本机 Qdrant（无需重新嵌入）
        </span>
        <input ref={kbRef} type="file" accept=".zip" hidden
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onImport(f); }} />
      </div>

      {err && <div className="text-red-600 text-sm">{err}</div>}
      {msg && <div className="text-emerald-600 text-sm">{msg}</div>}

      <table className="w-full bg-white rounded-lg overflow-hidden text-sm">
        <thead className="bg-slate-100 text-slate-600">
          <tr><th className="text-left p-3">文件名</th><th className="text-left p-3">大小</th>
            <th className="text-left p-3">collection</th><th className="text-left p-3">切分参数</th>
            <th className="text-left p-3">状态</th><th className="p-3">操作</th></tr>
        </thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.name} className="border-t border-slate-100 align-top">
              <td className="p-3">{d.name}</td>
              <td className="p-3 whitespace-nowrap">{(d.size_bytes / 1024).toFixed(1)} KB</td>
              <td className="p-3 text-slate-500">{d.collection}</td>
              <td className="p-3 text-slate-500 text-xs">
                {d.params
                  ? `size ${d.params.chunk_size} · overlap ${d.params.chunk_overlap}${d.params.prepend_heading_path ? " · +标题路径" : ""}`
                  : <span className="text-slate-300">未设置（去「切分分析」）</span>}
              </td>
              <td className="p-3"><StatusBadge d={d} /></td>
              <td className="p-3 text-center space-x-3 whitespace-nowrap">
                <a className="text-indigo-600" href={api.downloadUrl(d.name)}>下载</a>
                {d.status === "done" && (
                  <a className="text-emerald-600" href={api.exportKbUrl(d.collection)}>导出知识库</a>
                )}
                <button className="text-red-500" onClick={() => onDelete(d.name)}>删除</button>
              </td>
            </tr>
          ))}
          {docs.length === 0 && (
            <tr><td colSpan={6} className="p-6 text-center text-slate-400">暂无文档</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function StatusBadge({ d }: { d: Doc }) {
  const map: Record<string, [string, string]> = {
    new: ["未灌库", "bg-slate-100 text-slate-500"],
    ingesting: ["灌库中…", "bg-amber-100 text-amber-700"],
    done: [`已灌库 ${d.points_count ?? ""}块`, "bg-emerald-100 text-emerald-700"],
    error: ["失败", "bg-red-100 text-red-700"],
  };
  const [text, cls] = map[d.status || "new"] || map.new;
  return (
    <span className={`px-2 py-0.5 rounded text-xs ${cls}`} title={d.error || ""}>{text}</span>
  );
}
