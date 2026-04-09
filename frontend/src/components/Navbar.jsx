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
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between gap-4">
        <Link to="/" className="flex items-center gap-2 shrink-0">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect width="28" height="28" rx="6" fill="#632ca6"/>
            <text x="14" y="19" textAnchor="middle" fill="white" fontSize="14" fontWeight="bold" fontFamily="system-ui">D</text>
          </svg>
          <span className="font-bold text-lg text-gray-900 hidden sm:block">DD Store</span>
        </Link>

        <form onSubmit={handleSearch} className="flex-1 max-w-md">
          <div className="relative">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search products..."
              className="w-full pl-10 pr-4 py-2 rounded-lg bg-gray-50 border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#632ca6] focus:bg-white transition-colors"
            />
          </div>
        </form>

        <div className="flex items-center gap-1 text-sm font-medium text-gray-600">
          <Link to="/orders" className="hover:text-[#632ca6] hover:bg-gray-50 px-3 py-1.5 rounded-lg transition-colors hidden sm:block">Orders</Link>
          <Link to="/admin" className="hover:text-[#632ca6] hover:bg-gray-50 px-3 py-1.5 rounded-lg transition-colors hidden sm:block">Admin</Link>
          <Link to="/cart" className="relative hover:text-[#632ca6] hover:bg-gray-50 px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 100 4 2 2 0 000-4z" />
            </svg>
            {cartCount > 0 && (
              <span className="absolute -top-1 -right-0.5 bg-[#632ca6] text-white text-[10px] font-bold rounded-full w-4.5 h-4.5 min-w-[18px] flex items-center justify-center">
                {cartCount}
              </span>
            )}
          </Link>
        </div>
      </div>
    </nav>
  );
}
