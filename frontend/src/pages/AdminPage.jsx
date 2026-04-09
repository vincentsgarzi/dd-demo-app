import { useState, useEffect } from 'react';
import { api } from '../api';
import { logger } from '../datadog';

export default function AdminPage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [compute, setCompute] = useState(null);
  const [computing, setComputing] = useState(false);
  const [n, setN] = useState(50000);

  useEffect(() => {
    logger.info('Admin dashboard opened — fetching stats', { action: 'admin_opened' });

    api.getStats().then(s => {
      logger.info(`Dashboard stats loaded — ${s.total_orders} orders, ${s.total_products} products, $${s.total_revenue?.toFixed(2)} revenue`, {
        stats: { orders: s.total_orders, products: s.total_products, users: s.total_users, revenue: s.total_revenue, memory_leak_entries: s.memory_leak_entries },
        action: 'stats_loaded',
      });
      if (s.memory_leak_entries > 50) {
        logger.warn(`Memory leak detected — ${s.memory_leak_entries} entries in unbounded cache`, {
          stats: { memory_leak_entries: s.memory_leak_entries },
          action: 'memory_leak_warning',
        });
      }
      setStats(s);
    }).finally(() => setLoading(false));

    const interval = setInterval(() => {
      api.getStats().then(s => {
        logger.info('Stats auto-refreshed', {
          stats: { orders: s.total_orders, revenue: s.total_revenue, memory_leak_entries: s.memory_leak_entries },
          action: 'stats_refreshed',
        });
        setStats(s);
      });
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const runCompute = async () => {
    setComputing(true);
    setCompute(null);
    logger.warn(`CPU spike triggered — computing primes up to ${n.toLocaleString()} with naive algorithm`, {
      compute: { n, algorithm: 'naive_trial_division' },
      action: 'compute_triggered',
    });
    const start = performance.now();
    try {
      const result = await api.computePrimes(n);
      const elapsed = Math.round(performance.now() - start);
      setCompute(result);
      const level = elapsed > 5000 ? 'error' : elapsed > 2000 ? 'warn' : 'info';
      logger[level](`Prime computation complete — ${result.primes_found.toLocaleString()} primes found in ${elapsed}ms`, {
        compute: { n, primes_found: result.primes_found, elapsed_ms: elapsed, server_elapsed_ms: result.elapsed_ms },
        action: 'compute_complete',
      });
    } catch (err) {
      logger.error(`CPU spike computation failed: ${err.message}`, {
        compute: { n },
        error: { message: err.message },
        action: 'compute_failed',
      });
    } finally {
      setComputing(false);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Admin Dashboard</h1>
      <p className="text-sm text-yellow-700 bg-yellow-50 border border-yellow-200 rounded-xl px-4 py-2 mb-6 inline-block">
        ⚠️ This page intentionally triggers slow queries and a CPU spike button. Great for Datadog demos.
      </p>

      {/* Stats */}
      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8 animate-pulse">
          {[...Array(4)].map((_, i) => <div key={i} className="h-24 bg-gray-200 rounded-xl" />)}
        </div>
      ) : stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { label: 'Total Orders', value: stats.total_orders, icon: '📦' },
            { label: 'Products', value: stats.total_products, icon: '🛍️' },
            { label: 'Users', value: stats.total_users, icon: '👤' },
            { label: 'Revenue', value: `$${stats.total_revenue?.toFixed(2)}`, icon: '💰' },
          ].map(s => (
            <div key={s.label} className="bg-white border border-gray-100 rounded-xl p-4">
              <div className="text-2xl mb-1">{s.icon}</div>
              <div className="text-2xl font-bold text-gray-900">{s.value}</div>
              <div className="text-xs text-gray-500">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Memory leak indicator */}
      {stats && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-8">
          <h2 className="font-semibold text-red-700 mb-1">🚨 Memory Leak Detected</h2>
          <p className="text-sm text-red-600">
            Background worker has accumulated <strong>{stats.memory_leak_entries}</strong> entries in an unbounded list.
            This grows forever — watch it in the Datadog memory profiler!
          </p>
        </div>
      )}

      {/* CPU spike trigger */}
      <div className="bg-white border border-gray-100 rounded-xl p-6">
        <h2 className="font-semibold text-gray-900 mb-2">🔥 CPU Spike Demo</h2>
        <p className="text-sm text-gray-500 mb-4">
          Triggers a naive prime sieve (O(n√n), no cache). Watch the CPU spike in Datadog.
        </p>
        <div className="flex items-center gap-3">
          <input
            type="number"
            value={n}
            onChange={e => setN(Math.min(500000, Number(e.target.value)))}
            className="w-32 px-3 py-2 border border-gray-200 rounded-lg text-sm"
            step={10000}
            min={1000}
            max={500000}
          />
          <button
            onClick={runCompute}
            disabled={computing}
            className="px-4 py-2 bg-red-500 hover:bg-red-600 disabled:bg-red-300 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {computing ? '⏳ Computing…' : 'Trigger CPU spike'}
          </button>
          {compute && (
            <span className="text-sm text-gray-600">
              Found {compute.primes_found.toLocaleString()} primes in {compute.elapsed_ms}ms
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
