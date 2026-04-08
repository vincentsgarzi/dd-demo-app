import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api } from '../api';

export default function CartPage() {
  const [cart, setCart] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const load = () => api.getCart().then(setCart).finally(() => setLoading(false));

  useEffect(() => { load(); }, []);

  const clearCart = async () => {
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
            <img src={item.image_url} alt={item.name} className="w-16 h-16 object-cover rounded-lg bg-gray-100" />
            <div className="flex-1">
              <p className="font-medium text-gray-900 text-sm">{item.name}</p>
              <p className="text-gray-500 text-xs">Qty: {item.quantity}</p>
            </div>
            <span className="font-semibold text-gray-900">${(item.price * item.quantity).toFixed(2)}</span>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-4 mb-4">
        <div className="flex justify-between font-bold text-lg">
          <span>Total</span>
          <span>${cart.total.toFixed(2)}</span>
        </div>
      </div>

      <div className="flex gap-3">
        <button onClick={clearCart} className="px-4 py-2 border border-gray-200 rounded-xl text-sm text-gray-600 hover:bg-gray-50">
          Clear cart
        </button>
        <button
          onClick={() => navigate('/checkout')}
          className="flex-1 py-3 bg-purple-600 hover:bg-purple-700 text-white font-semibold rounded-xl transition-colors"
        >
          Subscribe →
        </button>
      </div>
    </div>
  );
}
