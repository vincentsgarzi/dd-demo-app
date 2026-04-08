import { useState, useEffect } from 'react';
import { api } from '../api';

const STATUS_COLOR = {
  completed: 'bg-green-100 text-green-700',
  confirmed: 'bg-blue-100 text-blue-700',
  shipped: 'bg-yellow-100 text-yellow-700',
  pending: 'bg-gray-100 text-gray-600',
};

export default function OrdersPage() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getOrders().then(setOrders).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-16 text-gray-400 animate-pulse">Loading orders…</div>;

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">My Subscriptions</h1>

      {orders.length === 0 ? (
        <p className="text-center text-gray-400 py-12">No orders yet.</p>
      ) : (
        <div className="space-y-3">
          {orders.map(order => (
            <div key={order.id} className="bg-white rounded-xl border border-gray-100 p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <span className="font-bold text-gray-900">#{order.id}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLOR[order.status] || 'bg-gray-100 text-gray-600'}`}>
                    {order.status}
                  </span>
                </div>
                <span className="font-bold text-gray-900">${order.total.toFixed(2)}</span>
              </div>
              <div className="text-xs text-gray-500 mb-2">{new Date(order.created_at).toLocaleDateString()}</div>
              <div className="flex flex-wrap gap-1">
                {order.items.map((item, i) => (
                  <span key={i} className="text-xs bg-gray-50 border border-gray-100 px-2 py-0.5 rounded">
                    {item.product_name} ×{item.quantity}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
