import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from '../../router';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ArrowLeftIcon,
  ArrowPathIcon,
  ArrowRightIcon,
  CheckIcon,
  ExclamationTriangleIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import AgentConnector from './AgentConnector';
import DatasetStep from './DatasetStep';
import MetricSelector from './MetricSelector';
import evaluatorApi, { errorMessage } from './evaluatorApi';

const steps = ['Metrics', 'Agent', 'Dataset', 'Review'];

export default function EvaluationWizard() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [metrics, setMetrics] = useState([]);
  const [agents, setAgents] = useState([]);
  const [datasets, setDatasets] = useState([]);
  const [runs, setRuns] = useState([]);
  const [selectedMetrics, setSelectedMetrics] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [metricConfig, setMetricConfig] = useState({ defaults: { threshold: 0.5, judge_model: 'gemini-2.5-flash' } });
  const [runName, setRunName] = useState('');
  const [message, setMessage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    setMessage(null);
    try {
      const [m, a, d, r] = await Promise.all([
        evaluatorApi.get('/metrics'),
        evaluatorApi.get('/agents'),
        evaluatorApi.get('/datasets'),
        evaluatorApi.get('/evaluations'),
      ]);
      setMetrics(m.data.metrics);
      if (m.data.default_judge_model) {
        setMetricConfig((state) => ({
          ...state,
          defaults: { ...state.defaults, judge_model: m.data.default_judge_model },
        }));
      }
      setAgents(a.data.agents);
      setDatasets(d.data.datasets);
      setRuns(r.data.runs);
    } catch (error) {
      const unavailable = !error.response;
      setMessage({
        ok: false,
        retry: true,
        text: unavailable
          ? 'The Agent Evaluator API is not reachable. Run start.bat from the project root, then retry the connection.'
          : errorMessage(error, 'The evaluator service could not load its workspace.'),
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadWorkspace(); }, [loadWorkspace]);

  const agent = useMemo(() => agents.find((item) => item.id === selectedAgent), [agents, selectedAgent]);
  const dataset = useMemo(() => datasets.find((item) => item.id === selectedDataset), [datasets, selectedDataset]);
  const selectedMetricObjects = useMemo(() => metrics.filter((item) => selectedMetrics.includes(item.id)), [metrics, selectedMetrics]);
  const canContinue = step === 0 ? selectedMetrics.length > 0 : step === 1 ? agent?.status === 'ready' : step === 2 ? Boolean(dataset) : true;

  const selectAgent = (value) => {
    setAgents((items) => items.some((item) => item.id === value.id) ? items.map((item) => item.id === value.id ? value : item) : [value, ...items]);
    setSelectedAgent(value.id);
  };
  const updateAgent = (value) => setAgents((items) => items.map((item) => item.id === value.id ? value : item));
  const selectDataset = (value) => {
    setDatasets((items) => items.some((item) => item.id === value.id) ? items : [value, ...items]);
    setSelectedDataset(value.id);
  };

  const startEvaluation = async () => {
    setStarting(true); setMessage(null);
    try {
      const response = await evaluatorApi.post('/evaluations', {
        name: runName.trim() || undefined,
        agent_id: selectedAgent,
        dataset_id: selectedDataset,
        metric_ids: selectedMetrics,
        metric_config: metricConfig,
      });
      navigate(`/runs/${response.data.id}`);
    } catch (error) { setMessage({ ok: false, text: errorMessage(error, 'Failed to start evaluation') }); }
    finally { setStarting(false); }
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="flex gap-2">{[0,.2,.4].map((delay) => <span key={delay} className="w-3 h-3 bg-primary rounded-full" style={{ animation: 'pulse-dot 1.2s infinite', animationDelay: `${delay}s` }} />)}</div></div>;

  return (
    <div className="min-h-screen bg-surface/40">
      <header className="h-[64px] px-6 lg:px-8 flex items-center justify-between border-b border-border bg-white sticky top-0 z-20">
        <div><h1 className="text-lg font-semibold text-text-primary">Agent Evaluator</h1><p className="text-xs text-text-secondary">DeepEval quality workspace</p></div>
        {runs.length > 0 && <button onClick={() => navigate(`/runs/${runs[0].id}`)} className="text-sm font-semibold text-primary hover:text-primary-hover">Latest dashboard</button>}
      </header>

      <div className="max-w-6xl mx-auto px-6 lg:px-8 py-8">
        <AnimatePresence>{message && <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className={`mb-5 p-4 rounded-btn border flex items-start justify-between gap-4 text-sm ${message.ok ? 'bg-green-50 border-green-200 text-green-800' : 'bg-red-50 border-red-200 text-red-700'}`}><span className="flex-1">{message.text}</span><div className="flex items-center gap-3">{message.retry && <button onClick={loadWorkspace} className="font-semibold underline underline-offset-2 whitespace-nowrap">Retry connection</button>}<button onClick={() => setMessage(null)} aria-label="Dismiss message"><XMarkIcon className="w-4 h-4" /></button></div></motion.div>}</AnimatePresence>

        <div className="mb-7 bg-white border border-border rounded-card px-5 py-4">
          <div className="flex items-center">
            {steps.map((label, index) => <div key={label} className={`flex items-center ${index < steps.length - 1 ? 'flex-1' : ''}`}><button onClick={() => index < step && setStep(index)} className="flex items-center gap-2 shrink-0"><span className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${index < step ? 'bg-success text-white' : index === step ? 'bg-primary text-white' : 'bg-gray-100 text-text-tertiary'}`}>{index < step ? <CheckIcon className="w-4 h-4" /> : index + 1}</span><span className={`hidden sm:block text-sm font-semibold ${index === step ? 'text-primary' : index < step ? 'text-text-primary' : 'text-text-tertiary'}`}>{label}</span></button>{index < steps.length - 1 && <span className={`h-px flex-1 mx-3 ${index < step ? 'bg-success' : 'bg-border'}`} />}</div>)}
          </div>
        </div>

        <motion.main key={step} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} className="bg-white border border-border rounded-card shadow-sm p-6 lg:p-8 min-h-[520px]">
          {step === 0 && <MetricSelector metrics={metrics} selected={selectedMetrics} onChange={setSelectedMetrics} metricConfig={metricConfig} setMetricConfig={setMetricConfig} />}
          {step === 1 && <AgentConnector agents={agents} selectedAgent={selectedAgent} onCreated={selectAgent} onUpdated={updateAgent} setMessage={setMessage} />}
          {step === 2 && <DatasetStep datasets={datasets} selectedDataset={selectedDataset} onCreated={selectDataset} setMessage={setMessage} />}
          {step === 3 && <div className="space-y-7"><div><h2 className="text-xl font-bold text-text-primary">Review and start evaluation</h2><p className="text-sm text-text-secondary mt-1">The agent runs once per case, then all selected metrics score the normalized result.</p></div><div><label className="block text-xs font-semibold text-text-secondary mb-1.5">Evaluation name</label><input value={runName} onChange={(event) => setRunName(event.target.value)} placeholder={`${agent?.name || 'Agent'} quality baseline`} className="w-full px-3 py-2.5 border border-border rounded-btn text-sm focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-primary" /></div><div className="grid md:grid-cols-3 gap-4"><ReviewCard label="Agent" value={agent?.name} detail={agent?.connection_type.replaceAll('_', ' ')} /><ReviewCard label="Dataset" value={dataset?.name} detail={`${dataset?.row_count || 0} cases`} /><ReviewCard label="Metrics" value={`${selectedMetrics.length} selected`} detail={selectedMetricObjects.map((item) => item.name).join(', ')} /></div><div className="grid md:grid-cols-2 gap-4 p-5 bg-surface border border-border rounded-card"><div><label className="block text-xs font-semibold text-text-secondary mb-1.5">Judge model</label><input value={metricConfig.defaults.judge_model} onChange={(event) => setMetricConfig((state) => ({ ...state, defaults: { ...state.defaults, judge_model: event.target.value } }))} className="w-full px-3 py-2.5 border border-border rounded-btn bg-white text-sm" /></div><div><label className="block text-xs font-semibold text-text-secondary mb-1.5">Passing threshold: {metricConfig.defaults.threshold}</label><input type="range" min="0" max="1" step="0.05" value={metricConfig.defaults.threshold} onChange={(event) => setMetricConfig((state) => ({ ...state, defaults: { ...state.defaults, threshold: Number(event.target.value) } }))} className="tpm-slider w-full h-2 mt-3 bg-gray-200 rounded-full" /></div></div><div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-btn text-sm text-amber-800"><ExclamationTriangleIcon className="w-5 h-5 shrink-0" /><p>LLM-as-a-judge metrics can incur provider cost. This run performs approximately <strong>{(dataset?.row_count || 0) * selectedMetrics.length}</strong> metric evaluations.</p></div></div>}
        </motion.main>

        <div className="mt-5 flex items-center justify-between">
          <button onClick={() => step > 0 && setStep(step - 1)} disabled={step === 0} className="px-4 py-2.5 rounded-btn text-sm font-semibold text-text-secondary hover:bg-white disabled:opacity-0 flex items-center gap-2"><ArrowLeftIcon className="w-4 h-4" />Back</button>
          {step < 3 ? <button onClick={() => canContinue && setStep(step + 1)} disabled={!canContinue} className="px-5 py-2.5 bg-primary hover:bg-primary-hover text-white rounded-btn text-sm font-semibold disabled:opacity-40 flex items-center gap-2">Continue<ArrowRightIcon className="w-4 h-4" /></button> : <button onClick={startEvaluation} disabled={starting} className="px-6 py-2.5 bg-primary hover:bg-primary-hover text-white rounded-btn text-sm font-semibold disabled:opacity-50 flex items-center gap-2">{starting && <ArrowPathIcon className="w-4 h-4 animate-spin" />}Start evaluation</button>}
        </div>
      </div>
    </div>
  );
}

function ReviewCard({ label, value, detail }) {
  return <div className="p-4 border border-border rounded-card"><p className="text-[10px] font-bold uppercase tracking-wider text-text-tertiary">{label}</p><p className="font-semibold text-text-primary mt-2">{value}</p><p className="text-xs text-text-secondary mt-1 line-clamp-2">{detail}</p></div>;
}
