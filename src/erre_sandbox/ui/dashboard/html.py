"""Static HTML/JS/CSS for the dashboard, embedded as a Python constant.

Shipping the UI inside a Python module (instead of a ``static/`` directory
mounted via :class:`~fastapi.staticfiles.StaticFiles`) keeps the dashboard
self-contained — no file-path resolution, no packaging subtleties — at the
cost of weaker editor syntax-highlighting. See decisions.md D4.

The page is intentionally plain HTML + one small Web Component
(``<ep-envelope-row>``). All other rendering is direct DOM manipulation.
"""

from __future__ import annotations

from typing import Final

HTML_TEMPLATE: Final[str] = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>ERRE-Sandbox Dashboard</title>
<style>
  :root { color-scheme: light dark; font-family: system-ui, sans-serif; }
  body { margin: 0; padding: 1rem; background: #111; color: #eee; }
  h1 { font-size: 1.1rem; margin: 0 0 .5rem 0; color: #9cf; }
  .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; }
  .panel { background: #1b1b1b; border: 1px solid #333; padding: .75rem;
           border-radius: 6px; min-height: 60vh; }
  .panel h2 { font-size: .9rem; margin: 0 0 .5rem 0; color: #9f9; }
  dl { display: grid; grid-template-columns: auto 1fr; gap: .25rem .75rem;
       font-size: .85rem; margin: 0; }
  dt { color: #888; }
  dd { margin: 0; }
  #stream { max-height: 60vh; overflow-y: auto; font-family: ui-monospace,
            SFMono-Regular, monospace; font-size: .75rem; }
  .kind { display: inline-block; width: 7em; font-weight: bold; }
  .k-handshake    { color: #9cf; }
  .k-agent_update { color: #9f9; }
  .k-speech       { color: #fc9; }
  .k-move         { color: #cf9; }
  .k-animation    { color: #9fc; }
  .k-world_tick   { color: #ccc; }
  .k-error        { color: #f77; }
  .alert { background: #3a1010; border-left: 3px solid #f55;
           padding: .25rem .5rem; margin: .25rem 0; font-size: .75rem; }
  .over-limit { color: #f66; font-weight: bold; }
  .meta { font-size: .7rem; color: #666; margin-top: .25rem; }
</style>
</head>
<body>
<h1>ERRE-Sandbox Dashboard (stub mode)</h1>
<div class="grid">
  <section class="panel" id="agent-panel">
    <h2>Agent</h2>
    <dl id="agent-dl"><dt>—</dt><dd>waiting…</dd></dl>
  </section>
  <section class="panel" id="stream-panel">
    <h2>Envelope Stream (tail)</h2>
    <div id="stream"></div>
  </section>
  <section class="panel" id="metrics-panel">
    <h2>Metrics</h2>
    <dl id="metrics-dl"><dt>samples</dt><dd id="m-samples">0</dd></dl>
    <h3 style="font-size:.8rem;color:#fc9;margin:.75rem 0 .25rem 0;">
      Alerts
    </h3>
    <div id="alerts"></div>
  </section>
</div>

<script>
(() => {
  const agentDl = document.getElementById('agent-dl');
  const stream  = document.getElementById('stream');
  const mSamples = document.getElementById('m-samples');
  const metricsDl = document.getElementById('metrics-dl');
  const alertsBox = document.getElementById('alerts');

  // Web Component: one row of the envelope stream.
  class EpEnvelopeRow extends HTMLElement {
    connectedCallback() {
      const kind = this.getAttribute('kind') || '';
      const text = this.getAttribute('text') || '';
      const tick = this.getAttribute('tick') || '';
      this.innerHTML =
        `<span class="kind k-${kind}">${kind}</span>` +
        `<span>tick=${tick} ${text}</span>`;
    }
  }
  customElements.define('ep-envelope-row', EpEnvelopeRow);

  const threshold = (k, cur, lim) => {
    return (cur !== null && lim !== null && cur > lim)
      ? `<span class="over-limit">${cur.toFixed(2)} / ${lim}</span>`
      : `${cur === null ? '—' : cur.toFixed(2)} / ${lim}`;
  };

  const renderAgent = (st) => {
    if (!st) { agentDl.innerHTML = '<dt>—</dt><dd>no agent yet</dd>'; return; }
    const rows = [
      ['agent_id', st.agent_id],
      ['persona', st.persona_id],
      ['tick', st.tick],
      ['zone', st.position?.zone],
      ['arousal', st.cognitive?.arousal?.toFixed(2)],
      ['valence', st.cognitive?.valence?.toFixed(2)],
      ['erre', st.erre?.current_mode],
    ];
    agentDl.innerHTML = rows
      .map(([k,v]) => `<dt>${k}</dt><dd>${v ?? '—'}</dd>`).join('');
  };

  const renderMetrics = (m) => {
    mSamples.textContent = m.sample_count;
    const kindCounts = Object.entries(m.envelope_kind_counts || {})
      .map(([k,n]) => `${k}:${n}`).join(' ');
    metricsDl.innerHTML = `
      <dt>samples</dt><dd>${m.sample_count}</dd>
      <dt>p50 ms</dt><dd>${threshold('p50', m.latency_p50_ms, 100)}</dd>
      <dt>p95 ms</dt><dd>${threshold('p95', m.latency_p95_ms, 250)}</dd>
      <dt>tick σ</dt><dd>${threshold('σ', m.tick_jitter_sigma, 0.20)}</dd>
      <dt>kinds</dt><dd class="meta">${kindCounts}</dd>`;
  };

  const appendEnvelope = (env) => {
    const row = document.createElement('ep-envelope-row');
    row.setAttribute('kind', env.kind);
    row.setAttribute('tick', env.tick);
    let text = '';
    if (env.kind === 'agent_update') text = `${env.agent_state?.agent_id}`;
    else if (env.kind === 'speech')   text = `"${(env.utterance||'').slice(0,40)}"`;
    else if (env.kind === 'move')     text = `→ zone=${env.target?.zone}`;
    else if (env.kind === 'animation')text = env.animation_name;
    else if (env.kind === 'error')    text = `${env.code}`;
    row.setAttribute('text', text);
    stream.prepend(row);
    while (stream.children.length > 50) stream.removeChild(stream.lastChild);
  };

  const pushAlert = (a) => {
    const div = document.createElement('div');
    div.className = 'alert';
    div.textContent = `⚠ ${a.which}: ${a.current.toFixed(2)} > ${a.limit}`;
    alertsBox.prepend(div);
    while (alertsBox.children.length > 10) alertsBox.removeChild(alertsBox.lastChild);
  };

  const ws = new WebSocket(
    (location.protocol === 'https:' ? 'wss://' : 'ws://') +
    location.host + '/ws/dashboard'
  );
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.kind === 'snapshot') {
      renderAgent(msg.agent_state);
      renderMetrics(msg.metrics);
      (msg.envelope_tail || []).slice().reverse().forEach(appendEnvelope);
      (msg.alerts || []).forEach(pushAlert);
    } else if (msg.kind === 'delta') {
      if (msg.envelope?.kind === 'agent_update') renderAgent(msg.envelope.agent_state);
      renderMetrics(msg.metrics);
      appendEnvelope(msg.envelope);
    } else if (msg.kind === 'alert') {
      pushAlert(msg.alert);
    }
  };
})();
</script>
</body>
</html>
"""


__all__ = ["HTML_TEMPLATE"]
