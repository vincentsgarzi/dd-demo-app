import { useState, useEffect, useRef } from 'react';
import { api } from '../api';
import { logger } from '../datadog';

const SERVICES = [
  { name: 'Gateway',   url: 'http://localhost:8080/api/health', port: '8080' },
  { name: 'Products',  url: 'http://localhost:8081/api/health', port: '8081' },
  { name: 'Orders',    url: 'http://localhost:8082/api/health', port: '8082' },
  { name: 'Analytics', url: 'http://localhost:8083/api/health', port: '8083' },
];

const BUGS = [
  { id: 'n1',       label: 'N+1 Query',              service: 'products', color: 'amber',   desc: 'GET /products fires 1 SELECT per product instead of a JOIN',              trigger: 'Every catalog load' },
  { id: 'null_desc',label: 'NULL Description Bug',   service: 'products', color: 'red',     desc: 'Product #3 has NULL description — .upper() raises AttributeError',         trigger: 'Product #3 detail or catalog' },
  { id: 'cdn',      label: 'Stale CDN Cache',        service: 'products', color: 'orange',  desc: 'product_id % 10 == 3 raises KeyError — schema v2.8 vs v3.2 mismatch',     trigger: 'Products ending in 3 or 13' },
  { id: 'ff',       label: 'Feature Flag Error',     service: 'products', color: 'red',     desc: 'product_id % 10 == 7 — archived variant pool raises RuntimeError',         trigger: 'Products ending in 7' },
  { id: 'es',       label: 'ES Circuit Breaker',     service: 'products', color: 'orange',  desc: '8% chance ConnectionError — Elasticsearch circuit breaker tripped',        trigger: '8% of product fetches' },
  { id: 'sagemaker',label: 'SageMaker Timeout',      service: 'products', color: 'amber',   desc: '5% chance TimeoutError — ML recommendation model unresponsive',            trigger: '5% of recommendation calls' },
  { id: 'pci',      label: 'PCI Vault Error',        service: 'orders',   color: 'red',     desc: 'ConnectionError — payment vault unreachable during tokenization',           trigger: '~8% of checkouts' },
  { id: 'idem',     label: 'Idempotency Violation',  service: 'orders',   color: 'orange',  desc: 'ValueError — duplicate order key detected in payment processor',           trigger: '~6% of checkouts' },
  { id: 'fraud',    label: 'Fraud Block',            service: 'orders',   color: 'amber',   desc: 'PermissionError — fraud scoring API blocked the transaction',              trigger: '~5% of checkouts' },
  { id: 'stripe',   label: 'Stripe Timeout',         service: 'orders',   color: 'red',     desc: 'TimeoutError — Stripe API exceeded 30s deadline during capture',           trigger: '~4% of checkouts' },
  { id: 'pipeline', label: 'Data Pipeline Stale',    service: 'analytics',color: 'amber',   desc: 'RuntimeError — Kafka consumer lag >5m SLA on stats-agg-v3 topic',         trigger: '7% of /stats fetches' },
  { id: 'memleak',  label: 'Memory Leak',            service: 'analytics',color: 'red',     desc: 'Background worker appends 10KB every 15s to a module-level list',         trigger: 'Always (capped at 500 entries)' },
  { id: 'rate',     label: 'Rate Limit Error',       service: 'gateway',  color: 'orange',  desc: 'PermissionError — 3% of POST/PUT requests exceed per-IP rate limit',      trigger: '3% of mutating requests' },
];

const STATUS_USERS = ['alice@acme.com', 'bob@globex.com', 'carol@initech.com', 'dave@umbrella.com', 'eve@hooli.com'];

function formatUptime(seconds) {
  if (!seconds) return '—';
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function formatTime(iso) {
  if (!iso) return '';
  const d = new Date(iso + 'Z');
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function timeAgo(iso) {
  const sec = Math.floor((Date.now() - new Date(iso + 'Z')) / 1000);
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  return `${Math.floor(sec / 3600)}h ago`;
}

// ── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({ label, value, sub, icon, gradient }) {
  return (
    <div className={`relative overflow-hidden rounded-2xl p-5 ${gradient}`}>
      <div className="text-2xl mb-3">{icon}</div>
      <div className="text-3xl font-bold text-white mb-0.5">{value}</div>
      <div className="text-sm font-medium text-white/80">{label}</div>
      {sub && <div className="text-xs text-white/55 mt-0.5">{sub}</div>}
    </div>
  );
}

// ── Service Health ───────────────────────────────────────────────────────────
function ServiceHealth() {
  const [statuses, setStatuses] = useState({});
  const [latencies, setLatencies] = useState({});

  useEffect(() => {
    const check = async () => {
      for (const svc of SERVICES) {
        const t0 = performance.now();
        try {
          const res = await fetch(svc.url, { signal: AbortSignal.timeout(2000) });
          const ms = Math.round(performance.now() - t0);
          setStatuses(s => ({ ...s, [svc.name]: res.ok ? 'up' : 'degraded' }));
          setLatencies(l => ({ ...l, [svc.name]: ms }));
        } catch {
          setStatuses(s => ({ ...s, [svc.name]: 'down' }));
          setLatencies(l => ({ ...l, [svc.name]: null }));
        }
      }
    };
    check();
    const t = setInterval(check, 8000);
    return () => clearInterval(t);
  }, []);

  const color = { up: 'text-emerald-600 bg-emerald-50 border-emerald-200', degraded: 'text-amber-600 bg-amber-50 border-amber-200', down: 'text-red-600 bg-red-50 border-red-200', undefined: 'text-gray-400 bg-gray-50 border-gray-200' };
  const dot = { up: 'bg-emerald-500 animate-pulse', degraded: 'bg-amber-500', down: 'bg-red-500', undefined: 'bg-gray-300' };

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5 mb-6">
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-semibold text-gray-700">Service Health</span>
        <span className="text-xs text-gray-400">auto-checks every 8s</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {SERVICES.map(svc => {
          const st = statuses[svc.name];
          const lat = latencies[svc.name];
          return (
            <div key={svc.name} className={`flex flex-col gap-1.5 px-4 py-3 rounded-xl border text-sm font-medium ${color[st]}`}>
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${dot[st]}`} />
                <span>{svc.name}</span>
              </div>
              <div className="text-xs opacity-70 font-normal flex justify-between">
                <span>:{svc.port}</span>
                <span>{lat ? `${lat}ms` : st === 'down' ? 'unreachable' : '…'}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Memory Leak Panel ────────────────────────────────────────────────────────
function MemoryLeakPanel({ stats }) {
  const pct = stats?.memory_leak_pct ?? 0;
  const entries = stats?.memory_leak_entries ?? 0;
  const mb = stats?.memory_leak_mb ?? 0;
  const cap = stats?.memory_leak_cap ?? 500;
  const uptime = stats?.worker_uptime_seconds ?? 0;
  const ratePerHour = stats?.leak_rate_entries_per_hour ?? 0;
  const capped = entries >= cap;

  const histRef = useRef([]);
  useEffect(() => {
    if (entries > 0) histRef.current = [...histRef.current.slice(-29), entries];
  }, [entries]);
  const hist = histRef.current;
  const maxH = Math.max(...hist, 1);
  const pts = hist.map((v, i) => `${(i / (hist.length - 1 || 1)) * 200},${40 - (v / maxH) * 36}`).join(' ');

  return (
    <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-50">
        <div className="flex items-center gap-3">
          <div className={`w-8 h-8 rounded-xl flex items-center justify-center text-base ${capped ? 'bg-orange-100' : 'bg-red-100'}`}>
            {capped ? '🔒' : '🧠'}
          </div>
          <div>
            <div className="text-sm font-semibold text-gray-900">Memory Leak — Unbounded Cache</div>
            <div className="text-xs text-gray-400">analytics worker · <code className="bg-gray-100 px-1 rounded text-xs">_leaked_memory[]</code></div>
          </div>
        </div>
        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${capped ? 'bg-orange-100 text-orange-700' : 'bg-red-100 text-red-600'}`}>
          {capped ? 'CAP REACHED' : 'LEAKING'}
        </span>
      </div>
      <div className="px-5 py-4">
        <div className="flex justify-between text-xs text-gray-500 mb-1.5">
          <span>{entries.toLocaleString()} / {cap.toLocaleString()} entries</span>
          <span>{mb.toFixed(2)} MB</span>
        </div>
        <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden mb-1">
          <div className={`h-full rounded-full transition-all duration-700 ${capped ? 'bg-gradient-to-r from-orange-400 to-orange-500' : 'bg-gradient-to-r from-red-400 to-red-500'}`} style={{ width: `${Math.min(pct, 100)}%` }} />
        </div>
        <div className="flex justify-between text-xs mb-4">
          <span className="text-gray-400">0 MB</span>
          <span className={`font-medium ${capped ? 'text-orange-600' : 'text-red-500'}`}>{pct.toFixed(1)}% of demo cap</span>
          <span className="text-gray-400">5 MB</span>
        </div>
        <div className="grid grid-cols-3 gap-3 mb-4">
          {[
            { v: formatUptime(uptime), l: 'worker uptime' },
            { v: `${ratePerHour.toFixed(0)}/hr`, l: 'entry rate' },
            { v: `${(ratePerHour * 10_000 / 1024 / 1024).toFixed(2)} MB/hr`, l: 'growth rate' },
          ].map(({ v, l }) => (
            <div key={l} className="bg-gray-50 rounded-xl p-3 text-center">
              <div className="text-base font-bold text-gray-900">{v}</div>
              <div className="text-xs text-gray-500">{l}</div>
            </div>
          ))}
        </div>
        {hist.length > 2 && (
          <div className="mb-4">
            <div className="text-xs text-gray-400 mb-1">Entry count over time</div>
            <svg viewBox="0 0 200 44" className="w-full h-10" preserveAspectRatio="none">
              <defs>
                <linearGradient id="lg1" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ef4444" stopOpacity="0.25"/>
                  <stop offset="100%" stopColor="#ef4444" stopOpacity="0"/>
                </linearGradient>
              </defs>
              <polygon points={`0,44 ${pts} 200,44`} fill="url(#lg1)"/>
              <polyline points={pts} fill="none" stroke="#ef4444" strokeWidth="1.5" strokeLinejoin="round"/>
            </svg>
          </div>
        )}
        <div className={`text-xs rounded-xl px-3 py-2.5 ${capped ? 'bg-orange-50 text-orange-700 border border-orange-100' : 'bg-red-50 text-red-700 border border-red-100'}`}>
          {capped
            ? <>✋ <strong>Capped at {cap} entries.</strong> Without this safety cap the process would consume ~400MB after a week of continuous demo use. Find the allocation in <strong>Datadog Profiler → Memory</strong>.</>
            : <>⚠️ Every 15s the worker appends a 10KB object with no eviction policy — GC cannot reclaim it. Visible in <strong>Datadog Profiler → Memory</strong>.</>
          }
        </div>
      </div>
    </div>
  );
}

// ── CPU Spike Panel ──────────────────────────────────────────────────────────
function CpuSpikePanel() {
  const [n, setN] = useState(50000);
  const [computing, setComputing] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);

  const run = async () => {
    setComputing(true);
    setResult(null);
    logger.warn(`CPU spike triggered — n=${n.toLocaleString()}`, { compute: { n }, action: 'compute_triggered' });
    const t0 = performance.now();
    try {
      const res = await api.computePrimes(n);
      const wall = Math.round(performance.now() - t0);
      if (Math.random() < 0.08) {
        document.getElementById('perf-heatmap-canvas').getContext('webgl2').createBuffer();
      }
      const entry = { n, primes: res.primes_found, serverMs: res.elapsed_ms, wallMs: wall, throttled: res.throttled, cpu: res.cpu_pct };
      setResult(entry);
      setHistory(h => [entry, ...h].slice(0, 6));
      const lvl = wall > 5000 ? 'error' : wall > 2000 ? 'warn' : 'info';
      logger[lvl](`Compute done — ${res.primes_found.toLocaleString()} primes in ${wall}ms`, { compute: { n, primes_found: res.primes_found, elapsed_ms: wall }, action: 'compute_complete' });
    } catch (err) {
      logger.error(`Compute failed: ${err.message}`, { action: 'compute_failed' });
    } finally {
      setComputing(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-gray-50">
        <div className="w-8 h-8 rounded-xl bg-orange-100 flex items-center justify-center text-base">🔥</div>
        <div>
          <div className="text-sm font-semibold text-gray-900">CPU Spike Demo</div>
          <div className="text-xs text-gray-400">Naive prime sieve · O(n√n) · no cache · visible in Datadog Profiler</div>
        </div>
      </div>
      <div className="px-5 py-4">
        <div className="flex flex-wrap gap-2 mb-3">
          {[10000, 30000, 50000, 75000].map(p => (
            <button key={p} onClick={() => setN(p)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${n === p ? 'bg-violet-600 text-white border-violet-600' : 'bg-white text-gray-600 border-gray-200 hover:border-violet-300'}`}>
              {p.toLocaleString()}
            </button>
          ))}
          <input type="number" value={n} onChange={e => setN(Math.min(75000, Math.max(1000, Number(e.target.value))))}
            className="w-28 px-3 py-1.5 border border-gray-200 rounded-lg text-xs text-gray-700 focus:outline-none focus:border-violet-400" step={5000}/>
        </div>
        <button onClick={run} disabled={computing}
          className="w-full py-3 rounded-xl font-semibold text-sm text-white transition-all bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600 disabled:from-gray-300 disabled:to-gray-300 disabled:cursor-not-allowed shadow-sm">
          {computing
            ? <span className="flex items-center justify-center gap-2"><svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.4 0 0 5.4 0 12h4z"/></svg>Computing n={n.toLocaleString()}…</span>
            : `🔥 Trigger CPU Spike (n=${n.toLocaleString()})`}
        </button>
        {result && (
          <div className={`mt-3 rounded-xl p-4 ${result.throttled ? 'bg-amber-50 border border-amber-100' : 'bg-emerald-50 border border-emerald-100'}`}>
            <div className="flex justify-between items-center mb-2">
              <span className={`text-xs font-semibold ${result.throttled ? 'text-amber-700' : 'text-emerald-700'}`}>
                {result.throttled ? '⚡ CPU Guard Throttled' : '✅ Complete'}
              </span>
              <span className="text-xs text-gray-400">host CPU: {result.cpu}%</span>
            </div>
            <div className="grid grid-cols-3 gap-3">
              {[
                { v: result.primes.toLocaleString(), l: 'primes found' },
                { v: `${result.serverMs}ms`, l: 'server time' },
                { v: `${result.wallMs}ms`, l: 'wall time' },
              ].map(({ v, l }) => (
                <div key={l}>
                  <div className="text-lg font-bold text-gray-900">{v}</div>
                  <div className="text-xs text-gray-500">{l}</div>
                </div>
              ))}
            </div>
          </div>
        )}
        {history.length > 0 && (
          <div className="mt-3">
            <div className="text-xs text-gray-400 mb-1.5">Run history</div>
            <div className="space-y-1">
              {history.map((h, i) => (
                <div key={i} className="flex items-center justify-between text-xs text-gray-600 bg-gray-50 rounded-lg px-3 py-1.5">
                  <span className="font-mono">n={h.n.toLocaleString()}</span>
                  <span>{h.primes.toLocaleString()} primes</span>
                  <span>{h.serverMs}ms</span>
                  {h.throttled && <span className="text-amber-600 font-medium">throttled</span>}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Live Order Feed ──────────────────────────────────────────────────────────
function LiveOrderFeed() {
  const [orders, setOrders] = useState([]);
  const [flash, setFlash] = useState(null);
  const prevCount = useRef(0);

  useEffect(() => {
    const fetch_ = () => api.getOrders().then(data => {
      const sorted = [...data].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 12);
      if (sorted.length > prevCount.current && prevCount.current > 0) {
        setFlash(sorted[0]?.id);
        setTimeout(() => setFlash(null), 1500);
      }
      prevCount.current = sorted.length;
      setOrders(sorted);
    }).catch(() => {});
    fetch_();
    const t = setInterval(fetch_, 4000);
    return () => clearInterval(t);
  }, []);

  const statusStyle = {
    confirmed: 'bg-emerald-100 text-emerald-700',
    pending:   'bg-amber-100 text-amber-700',
    failed:    'bg-red-100 text-red-700',
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-violet-100 flex items-center justify-center text-base">📋</div>
          <div>
            <div className="text-sm font-semibold text-gray-900">Live Order Feed</div>
            <div className="text-xs text-gray-400">most recent 12 orders · refreshes every 4s</div>
          </div>
        </div>
        <span className="flex items-center gap-1.5 text-xs text-emerald-600 font-medium">
          <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse"/>LIVE
        </span>
      </div>
      <div className="divide-y divide-gray-50">
        {orders.length === 0 && (
          <div className="px-5 py-8 text-center text-xs text-gray-400">Waiting for orders…</div>
        )}
        {orders.map(order => (
          <div key={order.id}
            className={`flex items-center justify-between px-5 py-3 transition-colors duration-500 ${flash === order.id ? 'bg-violet-50' : 'hover:bg-gray-50'}`}>
            <div className="flex items-center gap-3 min-w-0">
              <span className="text-xs font-mono text-gray-400 w-8">#{order.id}</span>
              <div className="min-w-0">
                <div className="text-xs font-medium text-gray-800 truncate max-w-48">
                  {order.items?.map(i => i.product_name).join(', ') || '—'}
                </div>
                <div className="text-xs text-gray-400">{STATUS_USERS[order.user_id - 1] ?? `user #${order.user_id}`} · {timeAgo(order.created_at)}</div>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusStyle[order.status] ?? 'bg-gray-100 text-gray-600'}`}>
                {order.status}
              </span>
              <span className="text-sm font-bold text-gray-900 w-16 text-right">${order.total?.toFixed(2)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Bug Arsenal ──────────────────────────────────────────────────────────────
const SERVICE_COLOR = { products: 'violet', orders: 'cyan', analytics: 'amber', gateway: 'rose' };

function BugArsenal() {
  const [expanded, setExpanded] = useState(null);
  const [filter, setFilter] = useState('all');
  const services = ['all', 'products', 'orders', 'analytics', 'gateway'];

  const shown = filter === 'all' ? BUGS : BUGS.filter(b => b.service === filter);

  const bugColor = {
    red:    { bg: 'bg-red-100',    text: 'text-red-700',    dot: 'bg-red-500',    badge: 'bg-red-50 text-red-600 border-red-200' },
    orange: { bg: 'bg-orange-100', text: 'text-orange-700', dot: 'bg-orange-500', badge: 'bg-orange-50 text-orange-600 border-orange-200' },
    amber:  { bg: 'bg-amber-100',  text: 'text-amber-700',  dot: 'bg-amber-500',  badge: 'bg-amber-50 text-amber-700 border-amber-200' },
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-red-100 flex items-center justify-center text-base">🐛</div>
          <div>
            <div className="text-sm font-semibold text-gray-900">Bug Arsenal</div>
            <div className="text-xs text-gray-400">{BUGS.length} intentional defects · all armed · great for demos</div>
          </div>
        </div>
        <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-red-50 text-red-600 border border-red-100">
          {BUGS.length} ACTIVE
        </span>
      </div>
      {/* Filter tabs */}
      <div className="flex gap-1 px-5 pt-3 pb-0 overflow-x-auto">
        {services.map(s => (
          <button key={s} onClick={() => setFilter(s)}
            className={`px-3 py-1 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${filter === s ? 'bg-violet-600 text-white' : 'text-gray-500 hover:bg-gray-100'}`}>
            {s === 'all' ? `All (${BUGS.length})` : `${s} (${BUGS.filter(b => b.service === s).length})`}
          </button>
        ))}
      </div>
      <div className="divide-y divide-gray-50 mt-2">
        {shown.map(bug => {
          const c = bugColor[bug.color];
          const isOpen = expanded === bug.id;
          return (
            <div key={bug.id} className="cursor-pointer" onClick={() => setExpanded(isOpen ? null : bug.id)}>
              <div className={`flex items-center justify-between px-5 py-3 transition-colors ${isOpen ? 'bg-gray-50' : 'hover:bg-gray-50'}`}>
                <div className="flex items-center gap-3 min-w-0">
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${c.dot} animate-pulse`}/>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-gray-800">{bug.label}</div>
                    <div className="text-xs text-gray-400">{bug.service} · {bug.trigger}</div>
                  </div>
                </div>
                <span className="text-gray-300 text-xs ml-2">{isOpen ? '▲' : '▼'}</span>
              </div>
              {isOpen && (
                <div className={`px-5 pb-3 text-xs text-gray-600 ${c.badge ? '' : ''}`}>
                  <div className={`rounded-xl px-4 py-3 border ${c.badge}`}>
                    {bug.desc}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────
export default function AdminPage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    logger.info('Admin dashboard opened', { action: 'admin_opened' });
    const fetch_ = () => api.getStats().then(s => {
      if (s.memory_leak_entries > 50) {
        logger.warn(`Memory leak: ${s.memory_leak_entries} entries (${s.memory_leak_mb}MB)`, {
          stats: { memory_leak_entries: s.memory_leak_entries, memory_leak_mb: s.memory_leak_mb },
          action: 'memory_leak_warning',
        });
      }
      setStats(s);
      setLoading(false);
    }).catch(() => setLoading(false));
    fetch_();
    const t = setInterval(fetch_, 5000);
    return () => clearInterval(t);
  }, []);

  const statCards = stats ? [
    { label: 'Total Orders',  value: stats.total_orders?.toLocaleString(),  sub: 'all time',             icon: '📦', gradient: 'bg-gradient-to-br from-violet-500 to-violet-700' },
    { label: 'Products',      value: stats.total_products?.toLocaleString(), sub: 'in catalog',           icon: '🛍️', gradient: 'bg-gradient-to-br from-cyan-500 to-cyan-700' },
    { label: 'Active Users',  value: stats.total_users?.toLocaleString(),    sub: 'registered accounts',  icon: '👤', gradient: 'bg-gradient-to-br from-amber-400 to-orange-500' },
    { label: 'Revenue',       value: `$${stats.total_revenue?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, sub: 'completed orders only', icon: '💰', gradient: 'bg-gradient-to-br from-emerald-500 to-emerald-700' },
  ] : [];

  return (
    <div className="max-w-5xl mx-auto">
      {/* ── Page header ── explicitly styled div, NOT h1 (global CSS makes h1 56px + near-invisible) */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#111827', lineHeight: 1.2, letterSpacing: '-0.03em' }}>
            Admin Dashboard
          </div>
          <div style={{ fontSize: '0.8125rem', color: '#9ca3af', marginTop: '0.25rem' }}>
            Internal ops view · auto-refreshes every 5s
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', padding: '0.375rem 0.875rem', background: '#f5f3ff', border: '1px solid #ede9fe', borderRadius: '0.75rem', fontSize: '0.75rem', fontWeight: 600, color: '#7c3aed' }}>
          <span style={{ width: '0.375rem', height: '0.375rem', borderRadius: '50%', background: '#7c3aed', display: 'inline-block' }}/>
          Datadog Demo Page
        </div>
      </div>

      {/* ── Service health ── */}
      <ServiceHealth />

      {/* ── Stat cards ── */}
      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 animate-pulse">
          {[...Array(4)].map((_, i) => <div key={i} className="h-28 bg-gray-100 rounded-2xl" />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {statCards.map(s => <StatCard key={s.label} {...s} />)}
        </div>
      )}

      {/* ── Row 1: Memory + CPU ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-5">
        <MemoryLeakPanel stats={stats} />
        <CpuSpikePanel />
      </div>

      {/* ── Row 2: Orders + Bug Arsenal ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-5">
        <LiveOrderFeed />
        <BugArsenal />
      </div>

      {/* ── Footer note ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem', padding: '0.875rem 1rem', background: '#f9fafb', border: '1px solid #f3f4f6', borderRadius: '0.75rem', fontSize: '0.75rem', color: '#6b7280' }}>
        <span>ℹ️</span>
        <span>
          This page intentionally triggers <strong style={{ color: '#374151' }}>slow SQL queries</strong> (Python-side aggregation instead of SQL SUM) and exposes a <strong style={{ color: '#374151' }}>memory leak</strong> in the analytics worker.
          Both are observable in <strong style={{ color: '#374151' }}>Datadog APM → Traces</strong> and <strong style={{ color: '#374151' }}>Continuous Profiler</strong>.
        </span>
      </div>
    </div>
  );
}
