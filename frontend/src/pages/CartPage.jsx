import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api } from '../api';
import { logger } from '../datadog';

export default function CartPage() {
  const [cart, setCart] = useState({ items: [], total: 0 });
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

  if (loading) return <div className="text-center py-16 text-gray-400">Loading cart…</div>;

  if (cart.items.length === 0) return (
    <div className="text-center py-16">
      <div className="text-6xl mb-4">🛒</div>
      <h2 className="text-xl font-bold text-gray-700 mb-2">Your cart is empty</h2>
      <Link to="/" className="text-purple-600 hover:underline text-sm">Continue shopping</Link>
    </div>
  );

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Your Plan</h1>

      <div className="bg-white rounded-xl border border-gray-100 divide-y divide-gray-100 mb-4">
        {cart.items.map((item, i) => (
          <div key={i} className="flex items-center gap-4 p-4">
            <div
              className="w-12 h-12 rounded-lg flex items-center justify-center flex-shrink-0"
              style={{ background: `linear-gradient(135deg, ${item.image_url || '#632ca6'}, ${item.image_url || '#632ca6'}cc)` }}
            >
              <span className="text-white/60 text-xs font-bold">{item.name.split(' ').map(w => w[0]).join('').slice(0, 2)}</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-medium text-gray-900 text-sm truncate">{item.name}</p>
              <p className="text-gray-500 text-xs">{item.quantity} {item.quantity === 1 ? 'host' : 'hosts'} /mo</p>
            </div>
            <span className="font-semibold text-gray-900">${(item.price * item.quantity).toFixed(2)}</span>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-4 mb-4">
        <div className="flex justify-between items-baseline">
          <span className="font-bold text-lg text-gray-900">Monthly total</span>
          <div>
            <span className="font-bold text-lg text-gray-900">${cart.total.toFixed(2)}</span>
            <span className="text-xs text-gray-400 ml-1">/mo</span>
          </div>
        </div>
      </div>

      <div className="flex gap-3">
        <button onClick={clearCart} className="px-4 py-2 border border-gray-200 rounded-xl text-sm text-gray-600 hover:bg-gray-50">
          Clear cart
        </button>
        <button
          onClick={() => {
            logger.info(`Proceeding to checkout with ${cart.items.length} item(s), $${cart.total.toFixed(2)}`, {
              cart: { items: cart.items.length, total: cart.total },
              action: 'proceed_to_checkout',
            });
            navigate('/checkout');
          }}
          className="flex-1 py-3 bg-purple-600 hover:bg-purple-700 text-white font-semibold rounded-xl transition-colors"
        >
          Subscribe →
        </button>
      </div>
    </div>
  );
}
