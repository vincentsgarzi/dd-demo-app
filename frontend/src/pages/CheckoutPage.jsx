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

    // BUG: 6% chance of client-side session hydration crash
    if (Math.random() < 0.06) {
      const hydrateCheckoutSession = (email) => {
        const restorePaymentMethod = (sessionData) => {
          const token = JSON.parse(sessionStorage.getItem('__dd_checkout_session'));
          return token.payment_methods.default.encrypted_token;
        };
        return restorePaymentMethod({ email });
      };
      hydrateCheckoutSession(email);
    }

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
    <div className="max-w-md mx-auto text-center py-16">
      <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-6">
        <svg className="w-8 h-8 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
        </svg>
      </div>
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Subscription Activated!</h1>
      <p className="text-gray-400 text-sm mb-1">Order #{order.order_id}</p>
      <p className="text-2xl font-bold text-[#632ca6] mb-8">${order.total.toFixed(2)}<span className="text-sm font-normal text-gray-400">/mo</span></p>
      <div className="flex gap-3 justify-center">
        <Link to="/orders" className="px-4 py-2.5 border border-gray-200 rounded-xl text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors">
          View orders
        </Link>
        <Link to="/" className="px-4 py-2.5 bg-[#632ca6] hover:bg-[#7c3aed] text-white rounded-xl text-sm font-medium transition-colors">
          Keep shopping
        </Link>
      </div>
    </div>
  );

  return (
    <div className="max-w-md mx-auto">
      <h1 className="text-xl font-bold text-gray-900 mb-6">Complete Your Subscription</h1>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-5 flex gap-3">
          <svg className="w-5 h-5 text-red-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div>
            <div className="text-sm font-semibold text-red-700">Payment failed</div>
            <div className="text-sm text-red-600 mt-0.5">{error}</div>
            <div className="text-xs text-red-400 mt-1">This is an intentional demo failure. Try again!</div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden" style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Email address</label>
            <input
              type="email"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@company.com"
              className="w-full px-4 py-3 border border-gray-200 rounded-xl text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-400 transition-all"
            />
          </div>

          {/* Fake payment section (UI only) */}
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Payment method</label>
            <div className="border border-gray-200 rounded-xl p-4 bg-gray-50">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-6 bg-gray-200 rounded animate-pulse" />
                <div className="flex-1 h-4 bg-gray-200 rounded animate-pulse" />
                <div className="w-12 h-4 bg-gray-200 rounded animate-pulse" />
              </div>
              <div className="text-xs text-gray-400 text-center">Payment form handled by Stripe (demo mode)</div>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 bg-[#632ca6] hover:bg-[#7c3aed] disabled:bg-gray-200 disabled:text-gray-400 text-white font-semibold rounded-xl transition-colors flex items-center justify-center gap-2 text-sm"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Processing payment…
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                Subscribe Now
              </>
            )}
          </button>
        </form>

        <div className="border-t border-gray-50 px-6 py-4 bg-gray-50/50">
          <div className="flex items-start gap-2.5 text-xs text-gray-400">
            <svg className="w-4 h-4 shrink-0 mt-0.5 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Demo environment. Payment processing intentionally fails ~17% of the time to generate Datadog Error Tracking events.
          </div>
        </div>
      </div>
    </div>
  );
}
