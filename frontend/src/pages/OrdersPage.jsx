import { useState, useEffect } from 'react';
import { api } from '../api';
import { logger } from '../datadog';

const STATUS_CONFIG = {
  completed: { label: 'Completed', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  confirmed: { label: 'Confirmed', cls: 'bg-blue-50 text-blue-700 border-blue-200' },
  shipped:   { label: 'Shipped',   cls: 'bg-violet-50 text-violet-700 border-violet-200' },
  pending:   { label: 'Pending',   cls: 'bg-amber-50 text-amber-700 border-amber-200' },
  failed:    { label: 'Failed',    cls: 'bg-red-50 text-red-600 border-red-200' },
};

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function OrdersPage() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const start = performance.now();
    logger.info('Loading order history', { action: 'orders_requested' });

    api.getOrders().then(data => {
      const elapsed = Math.round(performance.now() - start);
      const totalRevenue = data.reduce((sum, o) => sum + o.total, 0);
      const statusBreakdown = data.reduce((acc, o) => { acc[o.status] = (acc[o.status] || 0) + 1; return acc; }, {});
      logger.info(`Order history loaded — ${data.length} orders, $${totalRevenue.toFixed(2)} total revenue in ${elapsed}ms`, {
        orders: { count: data.length, total_revenue: totalRevenue, elapsed_ms: elapsed, status_breakdown: statusBreakdown },
        action: 'orders_loaded',
      });
      setOrders(data.sort((a, b) => new Date(b.created_at) - new Date(a.created_at)));
    }).catch(err => {
      logger.error(`Failed to load order history: ${err.message}`, {
        error: { message: err.message },
        action: 'orders_failed',
      });
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="animate-pulse space-y-3">
      <div className="h-6 bg-gray-100 rounded w-40 mb-6" />
      {[...Array(4)].map((_, i) => (
        <div key={i} className="bg-white rounded-xl border border-gray-100 p-5 space-y-2">
          <div className="flex justify-between">
            <div className="h-4 bg-gray-100 rounded w-24" />
            <div className="h-4 bg-gray-100 rounded w-16" />
          </div>
          <div className="h-3 bg-gray-100 rounded w-1/2" />
        </div>
      ))}
    </div>
  );

  const totalRevenue = orders.filter(o => o.status === 'completed').reduce((s, o) => s + o.total, 0);

  return (
    <div>
      {/* Header */}
      <div className="flex items-end justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">My Subscriptions</h1>
          <p className="text-sm text-gray-400 mt-0.5">{orders.length} order{orders.length !== 1 ? 's' : ''} total</p>
        </div>
        {orders.length > 0 && (
          <div className="text-right">
            <div className="text-xs text-gray-400">Total spend</div>
            <div className="text-lg font-bold text-gray-900 tabular-nums">${totalRevenue.toFixed(2)}</div>
          </div>
        )}
      </div>

      {orders.length === 0 ? (
        <div className="text-center py-20">
          <div className="w-14 h-14 rounded-2xl bg-gray-100 flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
          </div>
          <p className="text-sm font-medium text-gray-500 mb-1">No orders yet</p>
          <p className="text-xs text-gray-400">Complete a checkout to see your orders here.</p>
        </div>
      ) : (
        <div className="space-y-2.5">
          {orders.map(order => {
            const s = STATUS_CONFIG[order.status] || STATUS_CONFIG.pending;
            return (
              <div key={order.id} className="bg-white rounded-xl border border-gray-100 overflow-hidden hover:border-gray-200 transition-colors" style={{ boxShadow: '0 1px 2px rgba(0,0,0,0.04)' }}>
                <div className="flex items-center justify-between px-5 py-4">
                  <div className="flex items-center gap-4 min-w-0">
                    <div className="text-center">
                      <div className="text-[11px] font-mono text-gray-400">#{order.id}</div>
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-gray-900 truncate max-w-xs">
                        {order.items?.map(i => i.product_name).join(', ') || '—'}
                      </div>
                      <div className="text-xs text-gray-400 mt-0.5">{formatDate(order.created_at)}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0 ml-4">
                    <span className={`text-[11px] font-semibold px-2.5 py-1 rounded-full border ${s.cls}`}>
                      {s.label}
                    </span>
                    <span className="font-bold text-gray-900 text-sm tabular-nums w-20 text-right">${order.total.toFixed(2)}</span>
                  </div>
                </div>
                {order.items?.length > 0 && (
                  <div className="border-t border-gray-50 px-5 py-2.5 flex gap-1.5 flex-wrap">
                    {order.items.map((item, i) => (
                      <span key={i} className="text-[11px] bg-gray-50 border border-gray-100 text-gray-500 px-2 py-0.5 rounded-md">
                        {item.product_name} ×{item.quantity}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
