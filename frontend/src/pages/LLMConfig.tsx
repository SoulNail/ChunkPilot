import { useEffect, useState } from "react";
import { api } from "../api";

export default function LLMConfig() {
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [status, setStatus] = useState<any>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => { api.getLLM().then(setStatus).catch(() => {}); }, []);

  const save = async () => {
    setMsg("");
    try {
      const s = await api.setLLM({ base_url: baseUrl, api_key: apiKey, model });
      setStatus(s); setMsg("已保存");
    } catch (e: any) { setMsg(e.message); }
  };

  const test = async () => {
    setMsg("测试中…");
    try { const r = await api.testLLM(); setMsg(`连通成功：${r.model}`); }
    catch (e: any) { setMsg(e.message); }
  };

  return (
    <div className="max-w-xl space-y-4 bg-white p-6 rounded-lg">
      <h2 className="font-semibold">大模型配置（OpenAI 兼容）</h2>
      {status && (
        <div className="text-xs text-slate-500">
          当前：{status.configured ? `${status.model} @ ${status.base_url}（key ${status.api_key}）` : "未配置"}
        </div>
      )}
      <Field label="Base URL" placeholder="https://api.openai.com/v1" value={baseUrl} onChange={setBaseUrl} />
      <Field label="API Key" placeholder="sk-..." value={apiKey} onChange={setApiKey} type="password" />
      <Field label="模型名" placeholder="gpt-4o-mini / deepseek-chat ..." value={model} onChange={setModel} />
      <div className="flex gap-2">
        <button onClick={save} className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm">保存</button>
        <button onClick={test} className="px-4 py-2 border border-slate-300 rounded-md text-sm">测试连通</button>
      </div>
      {msg && <div className="text-sm text-slate-600">{msg}</div>}
    </div>
  );
}

function Field({ label, value, onChange, ...rest }: any) {
  return (
    <label className="block">
      <span className="text-sm text-slate-600">{label}</span>
      <input
        className="mt-1 w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
        value={value} onChange={(e) => onChange(e.target.value)} {...rest}
      />
    </label>
  );
}
