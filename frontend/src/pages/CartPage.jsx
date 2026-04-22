import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api } from '../api';
import { logger } from '../datadog';

export default function CartPage() {
  const [cart, setCart] = useState({ items: [], total: 0, count: 0 });
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const load = () => api.getCart().then(c => {
    logger.info(`Cart loaded — ${c.items.length} item(s), $${c.total.toFixed(2)} total`, {
      cart: { items: c.items.length, total: c.total, product_names: c.items.map(i => i.name) },
      action: 'cart_viewed',
    });
    setCart(c);
  }).finally(() => setLoading(false));

  useEffect(() => { load(); }, []);

  const clearCart = async () => {
    logger.info(`Clearing cart — abandoning ${cart.items.length} item(s) worth $${cart.total.toFixed(2)}`, {
      cart: { items: cart.items.length, total: cart.total, product_names: cart.items.map(i => i.name) },
      action: 'cart_cleared',
    });
    await api.clearCart();
    load();
  };

  if (loading) return (
    <div className="max-w-3xl mx-auto animate-pulse space-y-4 pt-4">
      <div className="h-6 bg-gray-100 rounded w-36 mb-8" />
      <div className="bg-white rounded-2xl border border-gray-100 divide-y divide-gray-50">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="flex items-center gap-4 p-5">
            <div className="w-12 h-12 bg-gray-100 rounded-xl flex-shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-gray-100 rounded w-1/2" />
              <div className="h-3 bg-gray-100 rounded w-1/4" />
            </div>
            <div className="h-5 bg-gray-100 rounded w-16" />
          </div>
        ))}
      </div>
    </div>
  );

  if (cart.items.length === 0) return (
    <div className="max-w-sm mx-auto text-center py-20">
      <div className="w-16 h-16 rounded-2xl bg-gray-100 flex items-center justify-center mx-auto mb-5">
        <svg className="w-8 h-8 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 100 4 2 2 0 000-4z" />
        </svg>
      </div>
      <h2 className="text-base font-semibold text-gray-900 mb-1.5">Your cart is empty</h2>
      <p className="text-sm text-gray-400 mb-6">Add some products to get started.</p>
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm font-medium text-white bg-[#632ca6] px-4 py-2.5 rounded-xl hover:bg-[#7c3aed] transition-colors">
        Browse products
      </Link>
    </div>
  );

  const tax = cart.total * 0.08;

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-xl font-bold text-gray-900 mb-6">Your Plan</h1>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Items */}
        <div className="lg:col-span-3">
          <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden" style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <div className="divide-y divide-gray-50">
              {cart.items.map((item, i) => {
                const accent = item.image_url || '#632ca6';
                const initials = item.name.split(' ').map(w => w[0]).join('').slice(0, 2);
                return (
                  <div key={i} className="flex items-center gap-4 px-5 py-4">
                    <div
                      className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0"
                      style={{ background: `linear-gradient(135deg, ${accent}, ${accent}cc)` }}
                    >
                      <span className="text-white text-xs font-bold">{initials}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900 text-sm truncate">{item.name}</p>
                      <p className="text-gray-400 text-xs mt-0.5">{item.quantity} {item.quantity === 1 ? 'host' : 'hosts'} /month</p>
                    </div>
                    <span className="font-semibold text-gray-900 text-sm tabular-nums">${(item.price * item.quantity).toFixed(2)}</span>
                  </div>
                );
              })}
            </div>
            <div className="border-t border-gray-50 px-5 py-3">
              <button
                onClick={clearCart}
                className="text-xs text-gray-400 hover:text-red-500 transition-colors"
              >
                Remove all items
              </button>
            </div>
          </div>
        </div>

        {/* Summary */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-2xl border border-gray-100 p-5" style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <h2 className="text-sm font-semibold text-gray-900 mb-4">Order Summary</h2>
            <div className="space-y-2.5 text-sm mb-4">
              <div className="flex justify-between text-gray-500">
                <span>Subtotal</span>
                <span className="tabular-nums">${cart.total.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-gray-500">
                <span>Tax (8%)</span>
                <span className="tabular-nums">${tax.toFixed(2)}</span>
              </div>
            </div>
            <div className="border-t border-gray-100 pt-3 mb-5">
              <div className="flex justify-between items-baseline">
                <span className="font-semibold text-gray-900">Monthly total</span>
                <div className="text-right">
                  <span className="font-bold text-lg text-gray-900 tabular-nums">${(cart.total + tax).toFixed(2)}</span>
                  <span className="text-xs text-gray-400 ml-1">/mo</span>
                </div>
              </div>
            </div>
            <button
              onClick={() => {
                logger.info(`Proceeding to checkout with ${cart.items.length} item(s), $${cart.total.toFixed(2)}`, {
                  cart: { items: cart.items.length, total: cart.total },
                  action: 'proceed_to_checkout',
                });
                navigate('/checkout');
              }}
              className="w-full py-3 bg-[#632ca6] hover:bg-[#7c3aed] text-white font-semibold text-sm rounded-xl transition-colors flex items-center justify-center gap-1.5"
            >
              Continue to checkout
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
            <div className="flex items-center justify-center gap-1.5 mt-3 text-xs text-gray-400">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
              Secured by Stripe
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
