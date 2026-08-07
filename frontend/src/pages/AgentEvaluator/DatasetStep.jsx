import { useRef, useState } from 'react';
import { ArrowDownTrayIcon, ArrowPathIcon, CheckCircleIcon, CloudArrowUpIcon, DocumentTextIcon } from '@heroicons/react/24/outline';
import evaluatorApi, { errorMessage } from './evaluatorApi';

export default function DatasetStep({ datasets, selectedDataset, onCreated, setMessage }) {
  const evaluatorBase = import.meta.env.VITE_EVALUATOR_API_URL || 'http://localhost:8002/api';
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState('');

  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    try {
      const data = new FormData(); data.append('file', file); if (name.trim()) data.append('name', name.trim());
      const response = await evaluatorApi.post('/datasets', data);
      onCreated(response.data);
      setMessage({ ok: true, text: `${response.data.row_count} evaluation cases validated and uploaded.` });
    } catch (error) { setMessage({ ok: false, text: errorMessage(error, 'Dataset upload failed') }); }
    finally { setBusy(false); }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div><h2 className="text-xl font-bold text-text-primary">Upload questions and ground truths</h2><p className="text-sm text-text-secondary mt-1">Only question/input is universally required. Add ground truth, context, tools, or turns when your selected metrics need them.</p></div>
        <div className="flex flex-wrap items-center gap-2">{['csv', 'jsonl', 'xlsx'].map((format) => <a key={format} href={`${evaluatorBase}/datasets/template.${format}`} download className="inline-flex items-center gap-1.5 px-3 py-2 rounded-btn border border-border bg-white text-xs font-semibold text-primary hover:border-primary hover:bg-primary-light"><ArrowDownTrayIcon className="w-4 h-4" />{format.toUpperCase()} template</a>)}</div>
      </div>

      <div className="grid md:grid-cols-[1fr_2fr] gap-5">
        <div>
          <label className="block text-xs font-semibold text-text-secondary mb-1.5">Dataset name (optional)</label>
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Refund policy benchmark" className="w-full px-3 py-2.5 rounded-btn border border-border text-sm focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-primary" />
          <div className="mt-4 p-4 rounded-card bg-surface border border-border">
            <p className="text-xs font-bold text-text-primary">Accepted column aliases</p>
            <dl className="mt-3 grid grid-cols-2 gap-y-2 text-xs">
              <dt className="text-text-secondary">question / prompt</dt><dd className="font-mono text-text-primary">input</dd>
              <dt className="text-text-secondary">ground_truth</dt><dd className="font-mono text-text-primary">expected_output</dd>
              <dt className="text-text-secondary">contexts</dt><dd className="font-mono text-text-primary">retrieval_context</dd>
              <dt className="text-text-secondary">tool_calls</dt><dd className="font-mono text-text-primary">tools_called</dd>
            </dl>
            <p className="text-[11px] leading-4 text-text-secondary mt-4"><span className="font-semibold text-text-primary">Question + ground truth is enough</span> for answer/reference metrics. RAG metrics additionally need retrieval context, tool metrics need tool fields, and conversational metrics need turns.</p>
          </div>
        </div>
        <button
          onClick={() => inputRef.current?.click()}
          onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => { event.preventDefault(); setDragging(false); upload(event.dataTransfer.files[0]); }}
          className={`min-h-[220px] border-2 border-dashed rounded-card flex flex-col items-center justify-center p-8 text-center transition-all ${dragging ? 'border-primary bg-primary-light' : 'border-border hover:border-blue-400 hover:bg-blue-50/30'}`}
        >
          {busy ? <ArrowPathIcon className="w-10 h-10 text-primary animate-spin" /> : <CloudArrowUpIcon className="w-10 h-10 text-primary" />}
          <p className="font-semibold text-text-primary mt-4">{busy ? 'Validating dataset…' : 'Drop your dataset here'}</p>
          <p className="text-xs text-text-secondary mt-2">or click to browse · .csv, .xlsx, .jsonl · up to 25 MB</p>
          <input ref={inputRef} type="file" accept=".csv,.xlsx,.jsonl" className="hidden" onChange={(event) => upload(event.target.files[0])} />
        </button>
      </div>

      {datasets.length > 0 && <div><h3 className="text-sm font-semibold text-text-primary mb-3">Available datasets</h3><div className="grid md:grid-cols-2 gap-3">{datasets.map((dataset) => {
        const active = selectedDataset === dataset.id;
        return <button key={dataset.id} onClick={() => onCreated(dataset)} className={`p-4 rounded-card border text-left ${active ? 'border-primary bg-primary-light' : 'border-border hover:border-blue-300'}`}><div className="flex items-start gap-3"><span className={`w-9 h-9 rounded-lg flex items-center justify-center ${active ? 'bg-primary text-white' : 'bg-surface text-text-tertiary'}`}>{active ? <CheckCircleIcon className="w-5 h-5" /> : <DocumentTextIcon className="w-5 h-5" />}</span><div className="min-w-0"><p className="font-semibold text-sm truncate">{dataset.name}</p><p className="text-xs text-text-secondary mt-1">{dataset.row_count} cases · {dataset.source_filename}</p><div className="flex flex-wrap gap-1 mt-2">{(dataset.columns || []).slice(0, 5).map((column) => <span key={column} className="px-1.5 py-0.5 bg-white border border-border rounded text-[9px] font-mono text-text-secondary">{column}</span>)}</div>{(dataset.warnings || []).map((warning) => <p key={warning} className="text-[10px] text-warning mt-2">{warning}</p>)}</div></div></button>;
      })}</div></div>}
    </div>
  );
}
