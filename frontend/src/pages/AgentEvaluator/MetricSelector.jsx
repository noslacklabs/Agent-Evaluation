import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  CheckCircleIcon,
  ChevronDownIcon,
  CircleStackIcon,
  CommandLineIcon,
  InformationCircleIcon,
  PuzzlePieceIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';

const categoryMeta = {
  Custom: { icon: SparklesIcon, color: 'text-violet-600', bg: 'bg-violet-50' },
  Agentic: { icon: CommandLineIcon, color: 'text-blue-600', bg: 'bg-blue-50' },
  'RAG — DeepEval': { icon: CircleStackIcon, color: 'text-emerald-600', bg: 'bg-emerald-50' },
  'Multi-Turn': { icon: PuzzlePieceIcon, color: 'text-amber-600', bg: 'bg-amber-50' },
  MCP: { icon: PuzzlePieceIcon, color: 'text-rose-600', bg: 'bg-rose-50' },
};

export default function MetricSelector({ metrics, selected, onChange, metricConfig, setMetricConfig }) {
  const [open, setOpen] = useState({ 'RAG — DeepEval': true, Agentic: true, Custom: true });
  const groups = useMemo(() => metrics.reduce((acc, item) => {
    (acc[item.category] ||= []).push(item);
    return acc;
  }, {}), [metrics]);

  const toggle = (item) => {
    if (item.availability !== 'ready') return;
    onChange(selected.includes(item.id) ? selected.filter((id) => id !== item.id) : [...selected, item.id]);
  };

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-text-primary">What should this agent be measured on?</h2>
          <p className="text-sm text-text-secondary mt-1">Select one or more DeepEval metrics. Requirements are checked again when your dataset is uploaded.</p>
        </div>
        <div className="shrink-0 px-3 py-1.5 rounded-full bg-primary-light text-primary text-xs font-bold">
          {selected.length} selected
        </div>
      </div>

      <div className="space-y-3">
        {Object.entries(groups).map(([category, items]) => {
          const meta = categoryMeta[category] || categoryMeta.Custom;
          const Icon = meta.icon;
          const isOpen = open[category] ?? false;
          const selectedCount = items.filter((item) => selected.includes(item.id)).length;
          return (
            <section key={category} className="border border-border rounded-card bg-white overflow-hidden">
              <button
                type="button"
                onClick={() => setOpen((state) => ({ ...state, [category]: !isOpen }))}
                className="w-full px-5 py-4 flex items-center justify-between hover:bg-surface transition-colors"
              >
                <span className="flex items-center gap-3">
                  <span className={`w-9 h-9 rounded-lg ${meta.bg} ${meta.color} flex items-center justify-center`}><Icon className="w-5 h-5" /></span>
                  <span className="text-left">
                    <span className="block font-semibold text-text-primary">{category}</span>
                    <span className="block text-xs text-text-secondary">{items.length} metrics{selectedCount ? ` · ${selectedCount} selected` : ''}</span>
                  </span>
                </span>
                <ChevronDownIcon className={`w-5 h-5 text-text-tertiary transition-transform ${isOpen ? 'rotate-180' : ''}`} />
              </button>
              {isOpen && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 px-4 pb-4 border-t border-border pt-4">
                  {items.map((item) => {
                    const active = selected.includes(item.id);
                    const ready = item.availability === 'ready';
                    return (
                      <motion.button
                        type="button"
                        key={item.id}
                        onClick={() => toggle(item)}
                        whileHover={ready ? { y: -2 } : undefined}
                        className={`text-left p-4 rounded-xl border transition-all ${active ? 'border-primary bg-primary-light shadow-sm' : ready ? 'border-border hover:border-blue-300 hover:shadow-sm bg-white' : 'border-border bg-surface opacity-65 cursor-not-allowed'}`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-sm text-text-primary">{item.name}</span>
                              {!ready && <span className="text-[10px] uppercase tracking-wide font-bold text-text-secondary bg-gray-200 px-1.5 py-0.5 rounded">{item.availability.replace('_', ' ')}</span>}
                            </div>
                            <p className="text-xs leading-5 text-text-secondary mt-1">{item.description}</p>
                          </div>
                          <span className={`w-5 h-5 rounded-full border flex items-center justify-center shrink-0 ${active ? 'bg-primary border-primary text-white' : 'border-gray-300'}`}>
                            {active && <CheckCircleIcon className="w-5 h-5" />}
                          </span>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-1.5">
                          {item.required_fields.map((field) => <span key={field} className="px-2 py-1 bg-white/80 border border-border rounded text-[10px] font-medium text-text-secondary">{field}</span>)}
                        </div>
                        {!ready && item.availability_note && <p className="mt-3 text-[11px] text-text-secondary flex gap-1.5"><InformationCircleIcon className="w-4 h-4 shrink-0" />{item.availability_note}</p>}
                      </motion.button>
                    );
                  })}
                </div>
              )}
            </section>
          );
        })}
      </div>

      {(selected.includes('g_eval') || selected.includes('conversational_g_eval')) && (
        <div className="p-5 border border-violet-200 bg-violet-50/60 rounded-card">
          <label className="block text-sm font-semibold text-text-primary mb-2">Custom evaluation criteria</label>
          <textarea
            rows={4}
            value={metricConfig.g_eval?.criteria || ''}
            onChange={(event) => setMetricConfig((state) => ({ ...state, g_eval: { ...state.g_eval, criteria: event.target.value }, conversational_g_eval: { ...state.conversational_g_eval, criteria: event.target.value } }))}
            placeholder="Example: Evaluate whether the response is factually correct, concise, professional, and fully addresses the ground truth."
            className="w-full px-3 py-2.5 rounded-btn border border-violet-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-200 focus:border-violet-400"
          />
        </div>
      )}

      {selected.includes('topic_adherence') && (
        <div className="p-5 border border-amber-200 bg-amber-50/60 rounded-card">
          <label className="block text-sm font-semibold text-text-primary mb-2">Allowed topics</label>
          <input
            value={(metricConfig.topic_adherence?.allowed_topics || []).join(', ')}
            onChange={(event) => setMetricConfig((state) => ({ ...state, topic_adherence: { allowed_topics: event.target.value.split(',').map((x) => x.trim()).filter(Boolean) } }))}
            placeholder="customer support, refunds, shipping"
            className="w-full px-3 py-2.5 rounded-btn border border-amber-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-amber-200"
          />
        </div>
      )}
    </div>
  );
}
