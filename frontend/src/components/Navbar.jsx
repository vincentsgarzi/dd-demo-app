import { Link, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { api } from '../api';

export default function Navbar() {
  const [cartCount, setCartCount] = useState(0);
  const [search, setSearch] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    api.getCart().then(c => setCartCount(c.count)).catch(() => {});
    const interval = setInterval(() => {
      api.getCart().then(c => setCartCount(c.count)).catch(() => {});
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    if (search.trim()) navigate(`/?q=${encodeURIComponent(search.trim())}`);
  };

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between gap-4">
        <Link to="/" className="flex items-center gap-2 shrink-0">
          {/* Datadog-style dog logo mark */}
          <span className="text-2xl">🐶</span>
          <span className="font-bold text-xl text-[#632ca6]">Datadog Marketplace</span>
        </Link>

        <form onSubmit={handleSearch} className="flex-1 max-w-md">
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search products…"
            className="w-full px-4 py-2 rounded-full border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-[#632ca6]"
          />
        </form>

        <div className="flex items-center gap-4 text-sm font-medium text-gray-600">
          <Link to="/orders" className="hover:text-[#632ca6] hidden sm:block">Orders</Link>
          <Link to="/admin" className="hover:text-[#632ca6] hidden sm:block">Admin</Link>
          <Link to="/cart" className="relative hover:text-[#632ca6]">
            🛒
            {cartCount > 0 && (
              <span className="absolute -top-2 -right-2 bg-[#632ca6] text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                {cartCount}
              </span>
            )}
          </Link>
        </div>
      </div>
    </nav>
  );
}
