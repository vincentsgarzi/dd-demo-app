import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api } from '../api';
import { logger } from '../datadog';

export default function CheckoutPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [order, setOrder] = useState(null);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    logger.info(`Checkout submitted for ${email} — processing payment`, {
      usr: { email },
      action: 'checkout_submitted',
    });

    const start = performance.now();
    try {
      const result = await api.checkout(email);
      const elapsed = Math.round(performance.now() - start);
      setOrder(result);
      logger.info(`Order #${result.order_id} confirmed — $${result.total.toFixed(2)} charged to ${email} in ${elapsed}ms`, {
        usr: { email },
        order: { id: result.order_id, total: result.total, elapsed_ms: elapsed },
        action: 'checkout_success',
      });
    } catch (err) {
      const elapsed = Math.round(performance.now() - start);
      const errorMsg = err.data?.error || err.message;
      setError(errorMsg);
      logger.error(`Checkout FAILED for ${email} after ${elapsed}ms — ${errorMsg}`, {
        usr: { email },
        error: { message: errorMsg, elapsed_ms: elapsed },
        action: 'checkout_failed',
      });
    } finally {
      setLoading(false);
    }
  };

  if (order) return (
    <div className="max-w-md mx-auto text-center py-12">
      <div className="text-6xl mb-4">🎉</div>
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Subscription Activated!</h1>
      <p className="text-gray-500 mb-2">Order #{order.order_id}</p>
      <p className="text-2xl font-bold text-purple-600 mb-6">${order.total.toFixed(2)}</p>
      <div className="flex gap-3 justify-center">
        <Link to="/orders" className="px-4 py-2 border border-gray-200 rounded-xl text-sm hover:bg-gray-50">
          View orders
        </Link>
        <Link to="/" className="px-4 py-2 bg-purple-600 text-white rounded-xl text-sm hover:bg-purple-700">
          Keep shopping
        </Link>
      </div>
    </div>
  );

  return (
    <div className="max-w-md mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Complete Your Subscription</h1>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-4 mb-4">
          <strong>Payment failed:</strong> {error}
          <p className="text-xs mt-1 text-red-500">This happens sometimes. Try again!</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-gray-100 p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-400"
          />
        </div>

        <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-500">
          💳 Demo card: 4242 4242 4242 4242 — may fail randomly (that's the point!)
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-300 text-white font-semibold rounded-xl transition-colors flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Processing…
            </>
          ) : 'Subscribe Now'}
        </button>
      </form>
    </div>
  );
}
