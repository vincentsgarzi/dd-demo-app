import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api';
import ProductCard from '../components/ProductCard';

export default function HomePage() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchParams] = useSearchParams();
  const q = searchParams.get('q');

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = q ? await api.searchProducts(q) : await api.getProducts();
      setProducts(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [q]);

  return (
    <div>
      {q ? (
        <h1 className="text-2xl font-bold text-gray-900 mb-6">
          Results for "<span className="text-[#632ca6]">{q}</span>"
          <span className="text-base font-normal text-gray-500 ml-2">({products.length} found)</span>
        </h1>
      ) : (
        <div className="mb-8">
          <h1 className="text-4xl font-extrabold text-[#632ca6]">Datadog Marketplace 🐶</h1>
          <p className="text-gray-500 mt-2">The only place to buy observability. Fully monitored by Datadog — including this sentence.</p>
        </div>
      )}

      {loading && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-100 overflow-hidden animate-pulse">
              <div className="aspect-[4/3] bg-gray-200" />
              <div className="p-4 space-y-2">
                <div className="h-3 bg-gray-200 rounded w-1/3" />
                <div className="h-4 bg-gray-200 rounded w-3/4" />
                <div className="h-3 bg-gray-200 rounded w-full" />
                <div className="h-8 bg-gray-200 rounded mt-2" />
              </div>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-4">
          <strong>Error:</strong> {error}
        </div>
      )}

      {!loading && !error && products.length === 0 && (
        <p className="text-gray-500 text-center py-16">No products found.</p>
      )}

      {!loading && !error && products.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {products.map(p => (
            <ProductCard key={p.id} product={p} onAdded={load} />
          ))}
        </div>
      )}
    </div>
  );
}
