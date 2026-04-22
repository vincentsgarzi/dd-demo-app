import { useState, useEffect, useRef } from 'react';
import { api } from '../api';
import { logger } from '../datadog';

const SERVICES = [
  { name: 'Gateway',  url: 'http://localhost:8080/api/health', key: 'ddstore-gateway' },
  { name: 'Products', url: 'http://localhost:8081/api/health', key: 'ddstore-products' },
  { name: 'Orders',   url: 'http://localhost:8082/api/health', key: 'ddstore-orders' },
  { name: 'Analytics',url: 'http://localhost:8083/api/health', key: 'ddstore-analytics' },
];

function formatUptime(seconds) {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function StatCard({ label, value, sub, icon, gradient, trend }) {
  return (
    <div className={`relative overflow-hidden rounded-2xl p-5 ${gradient}`}>
      <div className="flex items-start justify-between mb-3">
        <span className="text-2xl">{icon}</span>
        {trend !== undefined && (
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${trend >= 0 ? 'bg-white/20 text-white' : 'bg-white/20 text-white'}`}>
            {trend >= 0 ? '↑' : '↓'} {Math.abs(trend)}%
          </span>
        )}
      </div>
      <div className="text-3xl font-bold text-white mb-0.5">{value}</div>
      <div className="text-sm font-medium text-white/80">{label}</div>
      {sub && <div className="text-xs text-white/60 mt-0.5">{sub}</div>}
    </div>
  );
}

function ServicePill({ name, url }) {
  const [status, setStatus] = useState('checking');

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(url, { signal: AbortSignal.timeout(2000) });
        setStatus(res.ok ? 'up' : 'down');
      } catch {
        setStatus('down');
      }
    };
    check();
    const t = setInterval(check, 10000);
    return () => clearInterval(t);
  }, [url]);

  const colors = {
    up:       'bg-emerald-50 text-emerald-700 border-emerald-200',
    down:     'bg-red-50 text-red-700 border-red-200',
    checking: 'bg-gray-50 text-gray-400 border-gray-200',
  };
  const dot = {
    up:       'bg-emerald-500',
    down:     'bg-red-500',
    checking: 'bg-gray-300',
  };

  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-sm font-medium ${colors[status]}`}>
      <span className={`w-2 h-2 rounded-full ${dot[status]} ${status === 'up' ? 'animate-pulse' : ''}`} />
      {name}
      <span className="text-xs opacity-60 font-normal">{status === 'checking' ? '…' : status}</span>
    </div>
  );
}

function MemoryLeakPanel({ stats }) {
  const pct = stats?.memory_leak_pct ?? 0;
  const entries = stats?.memory_leak_entries ?? 0;
  const mb = stats?.memory_leak_mb ?? 0;
  const cap = stats?.memory_leak_cap ?? 500;
  const uptime = stats?.worker_uptime_seconds ?? 0;
  const ratePerHour = stats?.leak_rate_entries_per_hour ?? 0;
  const capped = entries >= cap;

  // track history for sparkline
  const historyRef = useRef([]);
  useEffect(() => {
    if (entries > 0) {
      historyRef.current = [...historyRef.current.slice(-29), entries];
    }
  }, [entries]);

  const history = historyRef.current;
  const maxH = Math.max(...history, 1);
  const sparkPoints = history.map((v, i) => {
    const x = (i / (history.length - 1 || 1)) * 200;
    const y = 40 - (v / maxH) * 36;
    return `${x},${y}`;
  }).join(' ');

  return (
    <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-50">
        <div className="flex items-center gap-3">
          <div className={`w-8 h-8 rounded-xl flex items-center justify-center text-base ${capped ? 'bg-orange-100' : 'bg-red-100'}`}>
            {capped ? '🔒' : '🧠'}
          </div>
          <div>
            <div className="font-semibold text-gray-900 text-sm">Memory Leak — Unbounded Cache</div>
            <div className="text-xs text-gray-400">analytics background worker · <code className="bg-gray-100 px-1 rounded">_leaked_memory[]</code></div>
          </div>
        </div>
        <div className={`text-xs font-semibold px-2.5 py-1 rounded-full ${capped ? 'bg-orange-100 text-orange-700' : 'bg-red-100 text-red-600'}`}>
          {capped ? 'CAP REACHED' : 'LEAKING'}
        </div>
      </div>

      <div className="px-6 py-5">
        {/* Progress bar */}
        <div className="mb-5">
          <div className="flex justify-between text-xs text-gray-500 mb-1.5">
            <span>{entries.toLocaleString()} entries / {cap.toLocaleString()} cap</span>
            <span>{mb.toFixed(2)} MB consumed</span>
          </div>
          <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${capped ? 'bg-gradient-to-r from-orange-400 to-orange-500' : 'bg-gradient-to-r from-red-400 to-red-600'}`}
              style={{ width: `${Math.min(pct, 100)}%` }}
            />
          </div>
          <div className="flex justify-between text-xs mt-1">
            <span className="text-gray-400">0 MB</span>
            <span className={`font-medium ${capped ? 'text-orange-600' : 'text-red-500'}`}>{pct.toFixed(1)}% of demo cap</span>
            <span className="text-gray-400">5 MB</span>
          </div>
        </div>

        {/* Metrics row */}
        <div className="grid grid-cols-3 gap-4 mb-5">
          <div className="bg-gray-50 rounded-xl p-3 text-center">
            <div className="text-lg font-bold text-gray-900">{formatUptime(uptime)}</div>
            <div className="text-xs text-gray-500">worker uptime</div>
          </div>
          <div className="bg-gray-50 rounded-xl p-3 text-center">
            <div className="text-lg font-bold text-gray-900">{ratePerHour.toFixed(0)}</div>
            <div className="text-xs text-gray-500">entries/hour</div>
          </div>
          <div className="bg-gray-50 rounded-xl p-3 text-center">
            <div className="text-lg font-bold text-gray-900">~{(ratePerHour * 10_000 / 1024 / 1024).toFixed(2)}</div>
            <div className="text-xs text-gray-500">MB/hour growth</div>
          </div>
        </div>

        {/* Sparkline */}
        {history.length > 2 && (
          <div className="mb-4">
            <div className="text-xs text-gray-400 mb-1">Entry count over time</div>
            <svg viewBox="0 0 200 44" className="w-full h-10" preserveAspectRatio="none">
              <defs>
                <linearGradient id="leakGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ef4444" stopOpacity="0.3"/>
                  <stop offset="100%" stopColor="#ef4444" stopOpacity="0"/>
                </linearGradient>
              </defs>
              <polygon
                points={`0,44 ${sparkPoints} 200,44`}
                fill="url(#leakGrad)"
              />
              <polyline
                points={sparkPoints}
                fill="none"
                stroke="#ef4444"
                strokeWidth="1.5"
                strokeLinejoin="round"
              />
            </svg>
          </div>
        )}

        {/* Explanation */}
        <div className={`text-xs rounded-xl px-4 py-3 ${capped ? 'bg-orange-50 text-orange-700 border border-orange-100' : 'bg-red-50 text-red-700 border border-red-100'}`}>
          {capped
            ? <>✋ <strong>Capped at {cap} entries (~5MB)</strong> — bug is fully demonstrated. Without this safety cap, this process would consume ~400MB after a week. Open <strong>Datadog Continuous Profiler → Memory</strong> to see the allocation site.</>
            : <>⚠️ <strong>Bug:</strong> every 15s the worker appends a 10KB object to a module-level list with no eviction policy. GC cannot reclaim it. Without a cap this would reach ~400MB in one week. Watch it grow in <strong>Datadog Continuous Profiler → Memory</strong>.</>
          }
        </div>
      </div>
    </div>
  );
}

function CpuSpikePanel() {
  const [n, setN] = useState(50000);
  const [computing, setComputing] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);

  const runCompute = async () => {
    setComputing(true);
    setResult(null);
    logger.warn(`CPU spike triggered — computing primes up to ${n.toLocaleString()} with naive algorithm`, {
      compute: { n, algorithm: 'naive_trial_division' },
      action: 'compute_triggered',
    });
    const wallStart = performance.now();
    try {
      const res = await api.computePrimes(n);
      const wallMs = Math.round(performance.now() - wallStart);

      // BUG: 8% chance of WebGL rendering context crash
      if (Math.random() < 0.08) {
        const initWebGLContext = (canvasId) => {
          const gl = document.getElementById(canvasId).getContext('webgl2');
          return gl.createBuffer();
        };
        initWebGLContext('perf-heatmap-canvas');
      }

      const entry = { n, primes: res.primes_found, serverMs: res.elapsed_ms, wallMs, throttled: res.throttled, cpu: res.cpu_pct };
      setResult(entry);
      setHistory(h => [entry, ...h].slice(0, 5));

      const level = wallMs > 5000 ? 'error' : wallMs > 2000 ? 'warn' : 'info';
      logger[level](`Prime computation complete — ${res.primes_found.toLocaleString()} primes in ${wallMs}ms`, {
        compute: { n, primes_found: res.primes_found, elapsed_ms: wallMs, server_ms: res.elapsed_ms, throttled: res.throttled },
        action: 'compute_complete',
      });
    } catch (err) {
      logger.error(`CPU spike failed: ${err.message}`, { compute: { n }, action: 'compute_failed' });
    } finally {
      setComputing(false);
    }
  };

  const presets = [10000, 30000, 50000, 75000];

  return (
    <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
      <div className="flex items-center gap-3 px-6 py-4 border-b border-gray-50">
        <div className="w-8 h-8 rounded-xl bg-orange-100 flex items-center justify-center text-base">🔥</div>
        <div>
          <div className="font-semibold text-gray-900 text-sm">CPU Spike Demo</div>
          <div className="text-xs text-gray-400">Naive prime sieve · O(n√n) · no cache · triggers Datadog profiler spike</div>
        </div>
      </div>

      <div className="px-6 py-5">
        {/* Presets + custom */}
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          {presets.map(p => (
            <button
              key={p}
              onClick={() => setN(p)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${n === p ? 'bg-violet-600 text-white border-violet-600' : 'bg-white text-gray-600 border-gray-200 hover:border-violet-300'}`}
            >
              n={p.toLocaleString()}
            </button>
          ))}
          <input
            type="number"
            value={n}
            onChange={e => setN(Math.min(75000, Math.max(1000, Number(e.target.value))))}
            className="w-28 px-3 py-1.5 border border-gray-200 rounded-lg text-xs text-gray-700 focus:outline-none focus:border-violet-400"
            step={5000}
          />
        </div>

        <button
          onClick={runCompute}
          disabled={computing}
          className="w-full py-3 rounded-xl font-semibold text-sm transition-all
            bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600
            disabled:from-gray-300 disabled:to-gray-300 disabled:cursor-not-allowed
            text-white shadow-sm shadow-orange-200"
        >
          {computing ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.4 0 0 5.4 0 12h4z"/>
              </svg>
              Computing n={n.toLocaleString()}…
            </span>
          ) : `🔥 Trigger CPU Spike  (n=${n.toLocaleString()})`}
        </button>

        {/* Latest result */}
        {result && (
          <div className={`mt-4 rounded-xl p-4 ${result.throttled ? 'bg-amber-50 border border-amber-100' : 'bg-emerald-50 border border-emerald-100'}`}>
            <div className="flex items-center justify-between mb-2">
              <span className={`text-xs font-semibold ${result.throttled ? 'text-amber-700' : 'text-emerald-700'}`}>
                {result.throttled ? '⚡ CPU Guard Throttled' : '✅ Computation Complete'}
              </span>
              <span className="text-xs text-gray-400">host CPU: {result.cpu}%</span>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <div className="text-lg font-bold text-gray-900">{result.primes.toLocaleString()}</div>
                <div className="text-xs text-gray-500">primes found</div>
              </div>
              <div>
                <div className="text-lg font-bold text-gray-900">{result.serverMs}ms</div>
                <div className="text-xs text-gray-500">server time</div>
              </div>
              <div>
                <div className="text-lg font-bold text-gray-900">{result.wallMs}ms</div>
                <div className="text-xs text-gray-500">wall time</div>
              </div>
            </div>
          </div>
        )}

        {/* History */}
        {history.length > 0 && (
          <div className="mt-4">
            <div className="text-xs text-gray-400 mb-2">Recent runs</div>
            <div className="space-y-1.5">
              {history.map((h, i) => (
                <div key={i} className="flex items-center justify-between text-xs text-gray-600 bg-gray-50 rounded-lg px-3 py-1.5">
                  <span>n={h.n.toLocaleString()}</span>
                  <span>{h.primes.toLocaleString()} primes</span>
                  <span>{h.serverMs}ms server</span>
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

export default function AdminPage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    logger.info('Admin dashboard opened', { action: 'admin_opened' });

    const fetchStats = () => api.getStats().then(s => {
      if (s.memory_leak_entries > 50) {
        logger.warn(`Memory leak: ${s.memory_leak_entries} entries (${s.memory_leak_mb}MB)`, {
          stats: { memory_leak_entries: s.memory_leak_entries, memory_leak_mb: s.memory_leak_mb },
          action: 'memory_leak_warning',
        });
      }
      setStats(s);
      setLoading(false);
    }).catch(() => setLoading(false));

    fetchStats();
    const t = setInterval(fetchStats, 5000);
    return () => clearInterval(t);
  }, []);

  const statCards = stats ? [
    {
      label: 'Total Orders',
      value: stats.total_orders?.toLocaleString(),
      sub: 'all time',
      icon: '📦',
      gradient: 'bg-gradient-to-br from-violet-500 to-violet-700',
    },
    {
      label: 'Products',
      value: stats.total_products?.toLocaleString(),
      sub: 'in catalog',
      icon: '🛍️',
      gradient: 'bg-gradient-to-br from-cyan-500 to-cyan-700',
    },
    {
      label: 'Active Users',
      value: stats.total_users?.toLocaleString(),
      sub: 'registered accounts',
      icon: '👤',
      gradient: 'bg-gradient-to-br from-amber-400 to-orange-500',
    },
    {
      label: 'Revenue',
      value: `$${stats.total_revenue?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      sub: 'completed orders only',
      icon: '💰',
      gradient: 'bg-gradient-to-br from-emerald-500 to-emerald-700',
    },
  ] : [];

  return (
    <div className="max-w-5xl mx-auto">
      {/* Page header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Admin Dashboard</h1>
          <p className="text-sm text-gray-400 mt-0.5">Internal ops view · auto-refreshes every 5s</p>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-violet-50 border border-violet-100 rounded-xl text-xs font-medium text-violet-700">
          <span className="w-1.5 h-1.5 rounded-full bg-violet-500 animate-pulse" />
          Datadog Demo Page
        </div>
      </div>

      {/* Service health */}
      <div className="mb-6">
        <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Service Health</div>
        <div className="flex flex-wrap gap-2">
          {SERVICES.map(s => <ServicePill key={s.key} name={s.name} url={s.url} />)}
        </div>
      </div>

      {/* Stat cards */}
      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8 animate-pulse">
          {[...Array(4)].map((_, i) => <div key={i} className="h-28 bg-gray-100 rounded-2xl" />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {statCards.map(s => <StatCard key={s.label} {...s} />)}
        </div>
      )}

      {/* Two-column panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <MemoryLeakPanel stats={stats} />
        <CpuSpikePanel />
      </div>

      {/* Performance note */}
      <div className="mt-6 flex items-start gap-3 px-4 py-3 bg-gray-50 rounded-xl border border-gray-100 text-xs text-gray-500">
        <span className="mt-0.5">ℹ️</span>
        <span>
          This page intentionally triggers <strong className="text-gray-700">slow SQL queries</strong> (Python-side aggregation instead of SQL SUM)
          and exposes a <strong className="text-gray-700">memory leak</strong> in the analytics worker.
          Both are observable in <strong className="text-gray-700">Datadog APM → Traces</strong> and <strong className="text-gray-700">Continuous Profiler</strong>.
        </span>
      </div>
    </div>
  );
}
