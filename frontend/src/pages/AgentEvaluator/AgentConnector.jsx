import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowPathIcon,
  CheckCircleIcon,
  CloudArrowUpIcon,
  CodeBracketIcon,
  CommandLineIcon,
  LinkIcon,
  ServerStackIcon,
  SignalIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import evaluatorApi, { errorMessage } from './evaluatorApi';

const connectorTypes = [
  { id: 'rest_api', name: 'Connect REST API', description: 'Request template and response mapping', icon: LinkIcon },
  { id: 'websocket', name: 'WebSocket Endpoint', description: 'Single responses or streamed events', icon: SignalIcon },
  { id: 'python_package', name: 'Upload Python Package', description: '.zip or .whl with an entrypoint', icon: CodeBracketIcon },
  { id: 'manifest', name: 'Agent Manifest', description: 'JSON or YAML auto-configuration', icon: CloudArrowUpIcon },
  { id: 'openai_compatible', name: 'OpenAI-Compatible', description: 'Base URL, API key, and model ID', icon: SparklesIcon },
  { id: 'framework', name: 'Framework Connector', description: 'Langflow, LangServe, FastAPI, webhook', icon: CommandLineIcon },
  { id: 'azure_openai', name: 'Azure OpenAI', description: 'Deployment via Responses or Chat', icon: ServerStackIcon },
  { id: 'microsoft_foundry', name: 'Microsoft Foundry Agent', description: 'Hosted agent with project endpoint', icon: ServerStackIcon },
];

const inputClass = 'w-full px-3 py-2.5 rounded-btn border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-primary';
const Label = ({ children }) => <label className="block text-xs font-semibold text-text-secondary mb-1.5">{children}</label>;
const Field = ({ label, ...props }) => <div><Label>{label}</Label><input className={inputClass} {...props} /></div>;

const initialForm = {
  name: '', endpoint_url: '', websocket_url: '', base_url: '', model: '', api_key: '', auth_type: 'none', auth_value: '',
  request_template: '{\n  "input": "{{input}}",\n  "session_id": "{{session_id}}"\n}',
  response_mapping: '{\n  "output": "output",\n  "retrieval_context": "retrieval_context",\n  "tools_called": "tools_called"\n}',
  entrypoint: 'agent:invoke', preset: 'langflow', flow_id: '', deployment: '', endpoint: '', api_type: 'responses',
  api_version: 'v1', auth_method: 'api_key', project_endpoint: '', agent_name: '', agent_id: '', agent_version: '', api_mode: 'responses',
  allow_private_network: false, session_mode: 'stateless', conversation_id: '', response_mode: 'single', done_path: 'type', done_value: 'done',
};

export default function AgentConnector({ agents, selectedAgent, onCreated, onUpdated, setMessage }) {
  const [mode, setMode] = useState(agents.length ? 'existing' : 'new');
  const [type, setType] = useState('rest_api');
  const [form, setForm] = useState(initialForm);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [testOutput, setTestOutput] = useState(null);

  const selected = useMemo(() => agents.find((item) => item.id === selectedAgent) || null, [agents, selectedAgent]);
  const set = (key) => (event) => setForm((state) => ({ ...state, [key]: event.target.type === 'checkbox' ? event.target.checked : event.target.value }));

  const parseJson = (value, label) => {
    try { return JSON.parse(value); } catch { throw new Error(`${label} must be valid JSON`); }
  };

  const buildRequest = () => {
    const common = { name: form.name, connection_type: type, config: {}, secrets: {} };
    if (type === 'rest_api') {
      common.config = { endpoint_url: form.endpoint_url, auth_type: form.auth_type, request_template: parseJson(form.request_template, 'Request template'), response_mapping: parseJson(form.response_mapping, 'Response mapping'), allow_private_network: form.allow_private_network };
      common.secrets = { auth_value: form.auth_value };
    } else if (type === 'websocket') {
      common.config = { websocket_url: form.websocket_url, auth_type: form.auth_type, request_template: parseJson(form.request_template, 'Request template'), response_mapping: parseJson(form.response_mapping, 'Response mapping'), response_mode: form.response_mode, done_path: form.done_path, done_value: form.done_value, allow_private_network: form.allow_private_network };
      common.secrets = { auth_value: form.auth_value };
    } else if (type === 'openai_compatible') {
      common.config = { base_url: form.base_url, model: form.model, allow_private_network: form.allow_private_network };
      common.secrets = { api_key: form.api_key };
    } else if (type === 'framework') {
      common.config = { preset: form.preset, base_url: form.base_url, flow_id: form.flow_id, allow_private_network: form.allow_private_network };
      common.secrets = { api_key: form.api_key, auth_value: form.api_key };
    } else if (type === 'azure_openai') {
      common.config = { endpoint: form.endpoint, deployment: form.deployment, api_type: form.api_type, api_version: form.api_version, auth_method: form.auth_method, allow_private_network: form.allow_private_network };
      common.secrets = form.auth_method === 'api_key' ? { api_key: form.api_key } : { entra_token: form.api_key };
    } else if (type === 'microsoft_foundry') {
      common.config = { project_endpoint: form.project_endpoint, agent_name: form.agent_name, agent_id: form.agent_id, agent_version: form.agent_version, api_mode: form.api_mode, api_version: form.api_version, session_mode: form.session_mode, conversation_id: form.session_mode === 'existing_conversation' ? form.conversation_id : undefined };
      common.secrets = { entra_token: form.api_key };
    }
    return common;
  };

  const create = async () => {
    setBusy(true); setTestOutput(null);
    try {
      let response;
      if (type === 'python_package') {
        if (!file) throw new Error('Choose a .zip or .whl package');
        const data = new FormData(); data.append('file', file); data.append('name', form.name); data.append('entrypoint', form.entrypoint);
        response = await evaluatorApi.post('/agents/python-package', data);
      } else if (type === 'manifest') {
        if (!file) throw new Error('Choose a JSON or YAML manifest');
        const data = new FormData(); data.append('file', file);
        response = await evaluatorApi.post('/agents/manifest', data);
      } else {
        if (!form.name.trim()) throw new Error('Agent name is required');
        response = await evaluatorApi.post('/agents', buildRequest());
      }
      onCreated(response.data);
      setMode('existing');
      setMessage({ ok: true, text: 'Agent connection saved. Run the connection test before continuing.' });
    } catch (error) {
      setMessage({ ok: false, text: errorMessage(error, 'Failed to save agent') });
    } finally { setBusy(false); }
  };

  const test = async () => {
    if (!selectedAgent) return;
    setBusy(true); setTestOutput(null);
    try {
      const response = await evaluatorApi.post(`/agents/${selectedAgent}/test`, { input: 'Reply with: evaluator connection ready' });
      setTestOutput({ ok: true, text: response.data.output });
      onUpdated({ ...selected, status: 'ready', last_test_message: 'Connection successful' });
    } catch (error) {
      setTestOutput({ ok: false, text: errorMessage(error, 'Connection test failed') });
      onUpdated({ ...selected, status: 'failed' });
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-text-primary">Connect the agent under test</h2>
        <p className="text-sm text-text-secondary mt-1">Every connector is converted to the evaluator's common response format before metrics run.</p>
      </div>

      <div className="inline-flex p-1 bg-surface border border-border rounded-lg">
        <button onClick={() => setMode('existing')} className={`px-4 py-2 rounded-md text-sm font-semibold ${mode === 'existing' ? 'bg-white text-primary shadow-sm' : 'text-text-secondary'}`}>Saved agents</button>
        <button onClick={() => setMode('new')} className={`px-4 py-2 rounded-md text-sm font-semibold ${mode === 'new' ? 'bg-white text-primary shadow-sm' : 'text-text-secondary'}`}>Add a connection</button>
      </div>

      {mode === 'existing' ? (
        <div className="space-y-4">
          {agents.length === 0 ? (
            <button onClick={() => setMode('new')} className="w-full py-14 border-2 border-dashed border-border rounded-card text-sm text-text-secondary hover:border-primary hover:text-primary">No agents yet. Add your first connection.</button>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {agents.map((agent) => (
                <button key={agent.id} onClick={() => { onCreated(agent); setTestOutput(null); }} className={`p-4 border rounded-card text-left transition-all ${selectedAgent === agent.id ? 'border-primary bg-primary-light shadow-sm' : 'border-border hover:border-blue-300'}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div><p className="font-semibold text-sm text-text-primary">{agent.name}</p><p className="text-xs text-text-secondary mt-1">{agent.connection_type.replaceAll('_', ' ')}</p></div>
                    <span className={`text-[10px] font-bold uppercase px-2 py-1 rounded-full ${agent.status === 'ready' ? 'bg-green-100 text-green-700' : agent.status === 'failed' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'}`}>{agent.status}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
          {selected && (
            <div className="p-5 border border-border rounded-card bg-surface/60 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div><p className="font-semibold text-sm">Connection test</p><p className="text-xs text-text-secondary mt-1">Sends one short prompt and validates the mapped assistant output.</p></div>
              <button onClick={test} disabled={busy} className="px-4 py-2 bg-primary text-white rounded-btn text-sm font-semibold flex items-center gap-2 disabled:opacity-50">{busy ? <ArrowPathIcon className="w-4 h-4 animate-spin" /> : <CheckCircleIcon className="w-4 h-4" />}Test connection</button>
            </div>
          )}
          {testOutput && <div className={`p-4 rounded-btn border text-sm ${testOutput.ok ? 'bg-green-50 border-green-200 text-green-800' : 'bg-red-50 border-red-200 text-red-700'}`}><p className="font-semibold">{testOutput.ok ? 'Connection successful' : 'Connection failed'}</p><p className="mt-1 break-words">{testOutput.text}</p></div>}
        </div>
      ) : (
        <div className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {connectorTypes.map((item) => <button key={item.id} onClick={() => { setType(item.id); setFile(null); }} className={`p-4 rounded-card border text-left ${type === item.id ? 'border-primary bg-primary-light' : 'border-border hover:border-blue-300'}`}><item.icon className={`w-5 h-5 ${type === item.id ? 'text-primary' : 'text-text-tertiary'}`} /><p className="font-semibold text-sm mt-3">{item.name}</p><p className="text-xs text-text-secondary mt-1">{item.description}</p></button>)}
          </div>

          <div className="border border-border rounded-card p-5 bg-white space-y-4">
            {type !== 'manifest' && <Field label="Connection name" value={form.name} onChange={set('name')} placeholder="Customer support agent" />}
            {type === 'rest_api' && <><div className="grid md:grid-cols-2 gap-4"><Field label="Endpoint URL" value={form.endpoint_url} onChange={set('endpoint_url')} placeholder="https://agent.example.com/invoke" /><div><Label>Authentication</Label><select className={inputClass} value={form.auth_type} onChange={set('auth_type')}><option value="none">None</option><option value="bearer">Bearer token</option><option value="api_key">API key header</option></select></div></div>{form.auth_type !== 'none' && <Field label="Credential" type="password" value={form.auth_value} onChange={set('auth_value')} />}<div className="grid md:grid-cols-2 gap-4"><div><Label>Request template</Label><textarea rows={7} className={`${inputClass} font-mono text-xs`} value={form.request_template} onChange={set('request_template')} /></div><div><Label>Response mapping</Label><textarea rows={7} className={`${inputClass} font-mono text-xs`} value={form.response_mapping} onChange={set('response_mapping')} /></div></div></>}
            {type === 'websocket' && <><div className="grid md:grid-cols-2 gap-4"><Field label="WebSocket URL" value={form.websocket_url} onChange={set('websocket_url')} placeholder="wss://agent.example.com/ws" /><div><Label>Authentication</Label><select className={inputClass} value={form.auth_type} onChange={set('auth_type')}><option value="none">None</option><option value="bearer">Bearer token</option><option value="api_key">API key header</option></select></div><div><Label>Response mode</Label><select className={inputClass} value={form.response_mode} onChange={set('response_mode')}><option value="single">Single message</option><option value="stream">Stream until completion event</option></select></div>{form.auth_type !== 'none' && <Field label="Credential" type="password" value={form.auth_value} onChange={set('auth_value')} />}</div>{form.response_mode === 'stream' && <div className="grid md:grid-cols-2 gap-4"><Field label="Completion event path" value={form.done_path} onChange={set('done_path')} placeholder="type" /><Field label="Completion event value" value={form.done_value} onChange={set('done_value')} placeholder="done" /></div>}<div className="grid md:grid-cols-2 gap-4"><div><Label>Message template</Label><textarea rows={7} className={`${inputClass} font-mono text-xs`} value={form.request_template} onChange={set('request_template')} /></div><div><Label>Response mapping</Label><textarea rows={7} className={`${inputClass} font-mono text-xs`} value={form.response_mapping} onChange={set('response_mapping')} /></div></div><p className="text-xs text-text-secondary">Streaming endpoints may send multiple JSON frames. Output values are combined until the completion event arrives.</p></>}
            {type === 'openai_compatible' && <div className="grid md:grid-cols-2 gap-4"><Field label="Base URL" value={form.base_url} onChange={set('base_url')} placeholder="https://example.com/v1" /><Field label="Model or agent ID" value={form.model} onChange={set('model')} placeholder="support-agent" /><Field label="API key" type="password" value={form.api_key} onChange={set('api_key')} /></div>}
            {type === 'framework' && <div className="grid md:grid-cols-2 gap-4"><div><Label>Framework preset</Label><select className={inputClass} value={form.preset} onChange={set('preset')}><option value="langflow">Langflow</option><option value="langserve">LangServe</option><option value="fastapi_agent">FastAPI agent</option><option value="custom_webhook">Custom webhook</option></select></div><Field label="Base URL" value={form.base_url} onChange={set('base_url')} placeholder="http://localhost:7860" />{form.preset === 'langflow' && <Field label="Flow ID" value={form.flow_id} onChange={set('flow_id')} />}<Field label="API key (optional)" type="password" value={form.api_key} onChange={set('api_key')} /></div>}
            {type === 'azure_openai' && <><div className="grid md:grid-cols-2 gap-4"><Field label="Azure endpoint" value={form.endpoint} onChange={set('endpoint')} placeholder="https://resource.openai.azure.com" /><Field label="Deployment name" value={form.deployment} onChange={set('deployment')} /><div><Label>API type</Label><select className={inputClass} value={form.api_type} onChange={set('api_type')}><option value="responses">Responses API</option><option value="chat_completions">Chat Completions</option></select></div><Field label="API version" value={form.api_version} onChange={set('api_version')} /><div><Label>Authentication</Label><select className={inputClass} value={form.auth_method} onChange={set('auth_method')}><option value="api_key">API key</option><option value="entra_token">Microsoft Entra bearer token</option></select></div><Field label={form.auth_method === 'api_key' ? 'API key' : 'Entra token'} type="password" value={form.api_key} onChange={set('api_key')} /></div><p className="text-xs text-text-secondary">Credentials are encrypted before they are written to the evaluator database.</p></>}
            {type === 'microsoft_foundry' && <div className="grid md:grid-cols-2 gap-4"><Field label="Project endpoint" value={form.project_endpoint} onChange={set('project_endpoint')} placeholder="https://resource.services.ai.azure.com/api/projects/project" /><div><Label>Foundry API mode</Label><select className={inputClass} value={form.api_mode} onChange={set('api_mode')}><option value="responses">Responses API (agent name)</option><option value="classic_threads">Classic threads/runs (agent ID)</option></select></div>{form.api_mode === 'responses' ? <Field label="Agent name" value={form.agent_name} onChange={set('agent_name')} /> : <Field label="Agent ID" value={form.agent_id} onChange={set('agent_id')} />}<Field label="Agent version (optional)" value={form.agent_version} onChange={set('agent_version')} /><Field label="Microsoft Entra bearer token" type="password" value={form.api_key} onChange={set('api_key')} /><Field label="API version" value={form.api_version} onChange={set('api_version')} />{form.api_mode === 'responses' && <><div><Label>Session preference</Label><select className={inputClass} value={form.session_mode} onChange={set('session_mode')}><option value="stateless">Stateless per test case</option><option value="existing_conversation">Use existing conversation</option></select></div>{form.session_mode === 'existing_conversation' && <Field label="Conversation ID" value={form.conversation_id} onChange={set('conversation_id')} />}</>}</div>}
            {type === 'python_package' && <div className="grid md:grid-cols-2 gap-4"><Field label="Entrypoint" value={form.entrypoint} onChange={set('entrypoint')} placeholder="agent:invoke" /><div><Label>Package (.zip or .whl)</Label><input type="file" accept=".zip,.whl" onChange={(event) => setFile(event.target.files[0])} className={`${inputClass} file:mr-3 file:border-0 file:bg-primary-light file:text-primary file:px-2 file:py-1 file:rounded`} /></div><p className="md:col-span-2 text-xs text-warning bg-amber-50 border border-amber-200 p-3 rounded-btn">Uploaded code runs in a timed subprocess. Use a containerized worker before enabling untrusted tenant uploads in production.</p></div>}
            {type === 'manifest' && <div><Label>Manifest (.json, .yaml, .yml)</Label><input type="file" accept=".json,.yaml,.yml" onChange={(event) => setFile(event.target.files[0])} className={`${inputClass} file:mr-3 file:border-0 file:bg-primary-light file:text-primary file:px-2 file:py-1 file:rounded`} /><p className="text-xs text-text-secondary mt-2">The manifest uses the same fields as the Agent API: name, connection_type, config, and secrets.</p></div>}
            {['rest_api', 'websocket', 'openai_compatible', 'framework', 'azure_openai'].includes(type) && <label className="flex items-center gap-2 text-xs text-text-secondary"><input type="checkbox" checked={form.allow_private_network} onChange={set('allow_private_network')} className="rounded" />Allow private/local network endpoint (required for localhost connectors)</label>}
            <div className="flex justify-end"><motion.button whileTap={{ scale: 0.98 }} onClick={create} disabled={busy} className="px-5 py-2.5 bg-primary hover:bg-primary-hover text-white rounded-btn text-sm font-semibold disabled:opacity-50 flex items-center gap-2">{busy && <ArrowPathIcon className="w-4 h-4 animate-spin" />}Save connection</motion.button></div>
          </div>
        </div>
      )}
    </div>
  );
}
