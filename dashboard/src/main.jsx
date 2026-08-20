import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const scenarios = ['A', 'B', 'C', 'D'];

function App() {
  const [summary, setSummary] = useState(null);
  const [selected, setSelected] = useState('A');
  const [loading, setLoading] = useState(false);

  async function refresh() {
    const response = await fetch('/api/dashboard/summary');
    setSummary(await response.json());
  }

  async function runScenario(scenario) {
    setSelected(scenario);
    setLoading(true);
    const response = await fetch('/api/simulation/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario, seed: 42 }),
    });
    setSummary(await response.json());
    setLoading(false);
  }

  useEffect(() => { refresh(); }, []);

  const metrics = summary || {};
  const pacing = metrics.pacing_log?.at(-1) || {};
  return (
    <main>
      <header>
        <div><span className="eyebrow">CREDRESOLVE / OPERATIONS</span><h1>SmartDialer control room</h1></div>
        <span className="live"><i /> SIMULATION LIVE</span>
      </header>
      <section className="hero">
        <div><p className="eyebrow">SCENARIO {selected}</p><h2>Capacity, safety, and provider health in one view.</h2><p className="muted">Read-only observability over the Python simulation backend. Every figure comes from an executed scenario.</p></div>
        <div className="scenario-tabs">{scenarios.map((scenario) => <button className={selected === scenario ? 'active' : ''} onClick={() => runScenario(scenario)} key={scenario}>Scenario {scenario}</button>)}</div>
      </section>
      <section className="stats">
        <Metric label="Calls initiated" value={metrics.total_calls_initiated ?? '—'} />
        <Metric label="Calls connected" value={metrics.total_calls_connected ?? '—'} />
        <Metric label="Answer rate" value={metrics.answer_rate == null ? '—' : `${(metrics.answer_rate * 100).toFixed(1)}%`} />
        <Metric label="Agent utilization" value={metrics.agent_utilization == null ? '—' : `${(metrics.agent_utilization * 100).toFixed(1)}%`} />
      </section>
      <section className="grid">
        <article className="panel wide"><div className="panel-head"><div><span className="eyebrow">PACING MONITOR</span><h3>Current recommendation</h3></div><span className={`badge ${pacing.safety_action === 'REDUCE' ? 'warn' : ''}`}>{pacing.safety_action || 'WAITING'}</span></div><div className="decision"><strong>{pacing.requested_calls ?? '—'}</strong><span>requested calls</span><div className="arrow">→</div><strong>{pacing.approved_calls ?? '—'}</strong><span>approved calls</span></div><p className="reason">{pacing.reason || 'Run a scenario to load a pacing decision.'}</p></article>
        <article className="panel"><span className="eyebrow">PROVIDER HEALTH</span><h3>Routing status</h3><Provider name="Provider A" healthy /><Provider name="Provider B" healthy={false} /></article>
        <article className="panel"><span className="eyebrow">RUN STATUS</span><h3>Scenario metrics</h3><Row label="Completed calls" value={metrics.total_calls_completed ?? '—'} /><Row label="Provider failures" value={metrics.provider_failures ?? '—'} /><Row label="Safety reductions" value={metrics.safety_reductions ?? '—'} /><Row label="Duplicate events" value={metrics.duplicate_provider_events ?? '—'} /></article>
      </section>
      {loading && <div className="toast">Running scenario {selected}...</div>}
    </main>
  );
}

function Metric({ label, value }) { return <div className="metric"><span>{label}</span><strong>{value}</strong></div>; }
function Row({ label, value }) { return <div className="row"><span>{label}</span><b>{value}</b></div>; }
function Provider({ name, healthy }) { return <div className="provider"><span><i className={healthy ? 'ok' : 'bad'} />{name}</span><b>{healthy ? 'HEALTHY' : 'DEGRADED'}</b></div>; }

createRoot(document.getElementById('root')).render(<App />);
