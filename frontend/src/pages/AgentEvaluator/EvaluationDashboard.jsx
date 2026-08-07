import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from '../../router';
import { motion } from 'framer-motion';
import {
  ArrowLeftIcon,
  ArrowPathIcon,
  ArrowDownTrayIcon,
  BeakerIcon,
  CheckCircleIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  Squares2X2Icon,
} from '@heroicons/react/24/outline';
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import evaluatorApi, { errorMessage } from './evaluatorApi';

const COLORS = ['#2563EB', '#7C3AED', '#0D9488', '#D97706', '#E11D48', '#65A30D', '#0891B2'];
const distributionColors = { excellent: '#059669', good: '#2563EB', needs_work: '#D97706' };
const score = (value) => value == null ? '—' : `${(value * 100).toFixed(1)}%`;
const number = (value) => value == null ? '—' : new Intl.NumberFormat().format(Math.round(value));

export default function EvaluationDashboard() {
  const { runId } = useParams();
  const [run, setRun] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [metricFilter, setMetricFilter] = useState('all');

  const load = useCallback(async () => {
    try { setRun((await evaluatorApi.get(`/evaluations/${runId}`)).data); setError(null); }
    catch (err) { setError(errorMessage(err, 'Failed to load evaluation dashboard')); }
    finally { setLoading(false); }
  }, [runId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!run || !['queued', 'running'].includes(run.status)) return;
    const timer = setInterval(load, 2000);
    return () => clearInterval(timer);
  }, [run?.status, load]);

  const summary = run?.summary || {};
  const metrics = summary.metrics || [];
  const resultRows = run?.results || [];
  const totalEvaluated = metrics.reduce((sum, item) => sum + item.evaluated, 0);
  const weightedPass = totalEvaluated ? metrics.reduce((sum, item) => sum + (item.pass_rate || 0) * item.evaluated, 0) / totalEvaluated : null;
  const filteredResults = metricFilter === 'all' ? resultRows : resultRows.filter((item) => item.metric_id === metricFilter);
  const metricNames = useMemo(() => [...new Set(resultRows.map((item) => item.metric_id))], [resultRows]);
  const caseData = useMemo(() => {
    const rows = new Map();
    resultRows.forEach((item) => { if (item.score == null) return; const row = rows.get(item.dataset_row) || { case: `#${item.dataset_row}` }; row[item.metric_id] = Number((item.score * 100).toFixed(1)); rows.set(item.dataset_row, row); });
    return [...rows.values()];
  }, [resultRows]);
  const distribution = Object.entries(summary.score_distribution || {}).map(([name, value]) => ({ name: name.replace('_', ' '), key: name, value }));
  const running = ['queued', 'running'].includes(run?.status);
  const progress = run?.progress_total ? (run.progress_current / run.progress_total) * 100 : 0;
  const evaluatorBase = import.meta.env.VITE_EVALUATOR_API_URL || 'http://localhost:8002/api';

  if (loading) return <div className="min-h-screen flex items-center justify-center"><ArrowPathIcon className="w-8 h-8 text-primary animate-spin" /></div>;
  if (error) return <div className="min-h-screen flex flex-col items-center justify-center p-8"><ExclamationTriangleIcon className="w-12 h-12 text-danger" /><h2 className="font-bold text-lg mt-4">Dashboard unavailable</h2><p className="text-sm text-text-secondary mt-2">{error}</p><Link to="/" className="mt-5 text-primary font-semibold text-sm">Back to evaluator</Link></div>;

  return (
    <div className="min-h-screen bg-surface/50">
      <header className="h-[64px] px-6 lg:px-8 flex items-center justify-between border-b border-border bg-white sticky top-0 z-20">
        <div className="flex items-center gap-3"><Link to="/" className="text-text-secondary hover:text-primary"><ArrowLeftIcon className="w-5 h-5" /></Link><div><h1 className="text-lg font-semibold text-text-primary">{run.name}</h1><p className="text-xs text-text-secondary">Evaluation dashboard</p></div></div>
        <div className="flex items-center gap-2"><a href={`${evaluatorBase}/evaluations/${runId}/report.pdf`} download className={`px-3 py-2 rounded-btn border border-border bg-white text-xs font-semibold text-primary flex items-center gap-2 hover:border-primary hover:bg-primary-light ${running ? 'pointer-events-none opacity-50' : ''}`} aria-disabled={running}><ArrowDownTrayIcon className="w-4 h-4" />Export PDF</a><div className={`px-3 py-1.5 rounded-full text-xs font-bold flex items-center gap-2 ${run.status === 'completed' ? 'bg-green-100 text-green-700' : run.status === 'failed' ? 'bg-red-100 text-red-700' : run.status === 'completed_with_errors' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'}`}>{running && <ArrowPathIcon className="w-3.5 h-3.5 animate-spin" />}{run.status.replaceAll('_', ' ')}</div></div>
      </header>

      <main className="max-w-[1500px] mx-auto px-6 lg:px-8 py-7 space-y-6">
        {running && <div className="p-5 bg-white border border-blue-200 rounded-card shadow-sm"><div className="flex items-center justify-between text-sm"><span className="font-semibold text-text-primary">Running agent and DeepEval metrics</span><span className="font-bold text-primary">{run.progress_current} / {run.progress_total} cases</span></div><div className="h-2 bg-blue-100 rounded-full overflow-hidden mt-3"><motion.div className="h-full bg-primary rounded-full" animate={{ width: `${progress}%` }} /></div><p className="text-xs text-text-secondary mt-3">Results appear here as each test case completes. You can leave this page and return later.</p></div>}
        {run.error && <div className="p-4 bg-red-50 border border-red-200 rounded-btn text-sm text-red-700">{run.error}</div>}

        <motion.div initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.06 } } }} className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          <Kpi icon={BeakerIcon} label="Overall score" value={score(summary.overall_score)} accent="blue" />
          <Kpi icon={CheckCircleIcon} label="Pass rate" value={score(weightedPass)} accent="green" />
          <Kpi icon={Squares2X2Icon} label="Cases scored" value={`${summary.scored_cases ?? run.progress_current}/${run.progress_total}`} accent="violet" />
          <Kpi icon={ClockIcon} label="Avg latency" value={summary.average_agent_latency_ms == null ? '—' : `${number(summary.average_agent_latency_ms)} ms`} accent="amber" />
          <Kpi icon={ExclamationTriangleIcon} label="Metric errors" value={number(summary.error_count || 0)} accent={summary.error_count ? 'rose' : 'green'} />
        </motion.div>

        <div className="grid lg:grid-cols-[2fr_1fr] gap-5">
          <Panel title="Metric scorecard" subtitle="Average score and pass threshold performance">
            {metrics.length ? <ResponsiveContainer width="100%" height={310}><BarChart data={metrics} margin={{ top: 12, right: 12, left: -10, bottom: 40 }}><CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} /><XAxis dataKey="metric_id" angle={-25} textAnchor="end" height={80} tick={{ fontSize: 10, fill: '#6B7280' }} /><YAxis domain={[0, 1]} tickFormatter={(v) => `${v * 100}%`} tick={{ fontSize: 11 }} /><Tooltip content={<ChartTooltip percent />} /><Bar dataKey="average_score" name="Average score" radius={[6, 6, 0, 0]}>{metrics.map((_, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}</Bar></BarChart></ResponsiveContainer> : <Empty />}
          </Panel>
          <Panel title="Score distribution" subtitle="All metric results across all cases">
            {distribution.some((item) => item.value) ? <ResponsiveContainer width="100%" height={310}><PieChart><Pie data={distribution} dataKey="value" nameKey="name" innerRadius={68} outerRadius={105} paddingAngle={3}>{distribution.map((item) => <Cell key={item.key} fill={distributionColors[item.key]} />)}</Pie><Tooltip /><Legend verticalAlign="bottom" formatter={(value) => <span className="text-xs capitalize text-text-secondary">{value}</span>} /></PieChart></ResponsiveContainer> : <Empty />}
          </Panel>
        </div>

        <Panel title="Scores by test case" subtitle="Use this view to spot regression clusters and outlier prompts">
          {caseData.length ? <ResponsiveContainer width="100%" height={350}><LineChart data={caseData} margin={{ top: 15, right: 25, left: -10, bottom: 5 }}><CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" /><XAxis dataKey="case" tick={{ fontSize: 11 }} /><YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} /><Tooltip content={<ChartTooltip suffix="%" />} /><Legend wrapperStyle={{ fontSize: 11 }} />{metricNames.slice(0, 8).map((metric, index) => <Line key={metric} type="monotone" dataKey={metric} stroke={COLORS[index % COLORS.length]} strokeWidth={2} dot={{ r: 3 }} connectNulls />)}</LineChart></ResponsiveContainer> : <Empty />}
        </Panel>

        <Panel title="Metric breakdown" subtitle="Coverage, pass rate, score range, and evaluation errors">
          <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b border-border text-left text-[10px] uppercase tracking-wider text-text-tertiary"><th className="py-3 pr-4">Metric</th><th className="py-3 px-4">Average</th><th className="py-3 px-4">Pass rate</th><th className="py-3 px-4">Range</th><th className="py-3 px-4">Evaluated</th><th className="py-3 pl-4">Errors</th></tr></thead><tbody>{metrics.map((item) => <tr key={item.metric_id} className="border-b border-border/70 last:border-0"><td className="py-3 pr-4 font-semibold text-text-primary">{item.metric_id.replaceAll('_', ' ')}</td><td className="py-3 px-4"><ScorePill value={item.average_score} /></td><td className="py-3 px-4">{score(item.pass_rate)}</td><td className="py-3 px-4 text-text-secondary">{score(item.min_score)} – {score(item.max_score)}</td><td className="py-3 px-4">{item.evaluated}</td><td className={`py-3 pl-4 ${item.errors ? 'text-danger font-semibold' : 'text-text-secondary'}`}>{item.errors}</td></tr>)}</tbody></table></div>
        </Panel>

        <Panel title="Case-level evidence" subtitle="Scores, judge reasoning, agent output, and errors for audit">
          <div className="mb-4 flex items-center gap-3"><label className="text-xs font-semibold text-text-secondary">Metric</label><select value={metricFilter} onChange={(event) => setMetricFilter(event.target.value)} className="px-3 py-2 border border-border rounded-btn bg-white text-xs"><option value="all">All metrics</option>{metricNames.map((name) => <option key={name} value={name}>{name.replaceAll('_', ' ')}</option>)}</select></div>
          <div className="overflow-x-auto max-h-[560px] overflow-y-auto"><table className="w-full min-w-[980px] text-xs"><thead className="sticky top-0 bg-white"><tr className="border-b border-border text-left text-[10px] uppercase tracking-wider text-text-tertiary"><th className="py-3 pr-3">Case</th><th className="py-3 px-3">Metric</th><th className="py-3 px-3">Score</th><th className="py-3 px-3 w-[24%]">Input</th><th className="py-3 px-3 w-[28%]">Agent output</th><th className="py-3 pl-3 w-[30%]">Reason / error</th></tr></thead><tbody>{filteredResults.map((item) => <tr key={item.id} className="border-b border-border/70 align-top"><td className="py-3 pr-3 font-mono text-text-secondary">#{item.dataset_row}</td><td className="py-3 px-3 font-semibold">{item.metric_id.replaceAll('_', ' ')}</td><td className="py-3 px-3"><ScorePill value={item.score} /></td><td className="py-3 px-3 text-text-secondary leading-5">{item.input_preview}</td><td className="py-3 px-3 text-text-secondary leading-5">{item.output_preview || '—'}</td><td className={`py-3 pl-3 leading-5 ${item.error ? 'text-danger' : 'text-text-secondary'}`}>{item.error || item.reason || '—'}</td></tr>)}</tbody></table>{!filteredResults.length && <Empty />}</div>
        </Panel>
      </main>
    </div>
  );
}

function Kpi({ icon: Icon, label, value, accent }) {
  const classes = { blue: 'bg-blue-50 text-blue-600', green: 'bg-green-50 text-green-600', violet: 'bg-violet-50 text-violet-600', amber: 'bg-amber-50 text-amber-600', rose: 'bg-rose-50 text-rose-600' };
  return <motion.div variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0 } }} className="p-4 bg-white border border-border rounded-card shadow-sm"><div className={`w-9 h-9 rounded-lg flex items-center justify-center ${classes[accent]}`}><Icon className="w-5 h-5" /></div><p className="text-2xl font-bold text-text-primary mt-4">{value}</p><p className="text-xs text-text-secondary mt-1">{label}</p></motion.div>;
}
function Panel({ title, subtitle, children }) { return <section className="bg-white border border-border rounded-card shadow-sm overflow-hidden"><div className="px-5 py-4 border-b border-border"><h2 className="font-semibold text-sm text-text-primary">{title}</h2><p className="text-xs text-text-secondary mt-1">{subtitle}</p></div><div className="p-5">{children}</div></section>; }
function Empty() { return <div className="h-[180px] flex items-center justify-center text-sm italic text-text-tertiary">Waiting for evaluation data…</div>; }
function ScorePill({ value }) { const color = value == null ? 'bg-gray-100 text-gray-500' : value >= .8 ? 'bg-green-100 text-green-700' : value >= .6 ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-700'; return <span className={`inline-flex px-2 py-1 rounded-full font-bold ${color}`}>{score(value)}</span>; }
function ChartTooltip({ active, payload, label, percent, suffix = '' }) { if (!active || !payload?.length) return null; return <div className="bg-white border border-border rounded-lg shadow-lg p-3 text-xs"><p className="font-semibold mb-2">{label}</p>{payload.map((item) => <p key={item.dataKey} className="py-0.5" style={{ color: item.color || item.fill }}>{item.name}: {percent ? score(item.value) : `${item.value}${suffix}`}</p>)}</div>; }
