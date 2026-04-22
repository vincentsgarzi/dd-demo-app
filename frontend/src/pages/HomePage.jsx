import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { logger } from '../datadog';
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
    const start = performance.now();
    try {
      if (q) {
        logger.info('Search initiated from storefront', { search: { query: q }, action: 'search_started' });
      } else {
        logger.info('Loading product catalog', { action: 'catalog_requested' });
      }

      const data = q ? await api.searchProducts(q) : await api.getProducts();
      const elapsed = Math.round(performance.now() - start);

      if (q) {
        logger.info(`Search for "${q}" returned ${data.length} result(s) in ${elapsed}ms`, {
          search: { query: q, results: data.length, elapsed_ms: elapsed },
          action: 'search_complete',
        });
      } else {
        const categories = [...new Set(data.map(p => p.category).filter(Boolean))];
        logger.info(`Catalog loaded — ${data.length} products across ${categories.length} categories in ${elapsed}ms`, {
          catalog: { product_count: data.length, categories: categories, category_count: categories.length, elapsed_ms: elapsed },
          action: 'catalog_loaded',
        });
      }
      // BUG: 4% chance of client-side personalization engine crash
      if (data.length > 5 && Math.random() < 0.04) {
        const applyPersonalization = (products, userProfile) => {
          const scoreProduct = (product, preferences) => {
            // Tries to access A/B test variant config that doesn't exist
            return product.personalization_config.variant_weights.score;
          };
          return products.map(p => ({ ...p, score: scoreProduct(p, userProfile) }));
        };
        applyPersonalization(data, { segment: 'returning', cohort: 'high_value' });
      }

      setProducts(data);
    } catch (err) {
      const elapsed = Math.round(performance.now() - start);
      logger.error(`Failed to load ${q ? `search results for "${q}"` : 'product catalog'} after ${elapsed}ms: ${err.message}`, {
        search: q ? { query: q } : undefined,
        error: { message: err.message, elapsed_ms: elapsed },
        action: q ? 'search_failed' : 'catalog_failed',
      });
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [q]);

  return (
    <div>
      {q ? (
        /* div not h1 — global CSS sets h1 to 56px + near-white color in dark color-scheme */
        <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#111827', marginBottom: '1.5rem' }}>
          Results for "<span style={{ color: '#632ca6' }}>{q}</span>"
          <span style={{ fontSize: '1rem', fontWeight: 400, color: '#6b7280', marginLeft: '0.5rem' }}>({products.length} found)</span>
        </div>
      ) : (
        <div className="mb-10">
          <div className="flex items-center gap-3 mb-2">
            {/* div not h1 — avoids global 56px + near-white h1 style */}
            <div style={{ fontSize: '2rem', fontWeight: 800, color: '#111827', lineHeight: 1.2, letterSpacing: '-0.03em' }}>
              DD Store
            </div>
            <span className="text-xs font-medium bg-[#632ca6] text-white px-2 py-0.5 rounded-full">DEMO</span>
          </div>
          <p className="text-gray-500 text-sm">Observability products, fully monitored by Datadog.</p>
        </div>
      )}

      {loading && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-100 overflow-hidden animate-pulse">
              <div className="aspect-[5/3] bg-gray-100" />
              <div className="p-4 space-y-2">
                <div className="h-3 bg-gray-100 rounded w-1/3" />
                <div className="h-4 bg-gray-100 rounded w-3/4" />
                <div className="h-3 bg-gray-100 rounded w-full" />
                <div className="h-8 bg-gray-100 rounded mt-2" />
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
