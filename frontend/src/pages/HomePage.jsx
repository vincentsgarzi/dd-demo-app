import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { logger } from '../datadog';
import ProductCard from '../components/ProductCard';

const CATEGORIES = ['All', 'Observability', 'Infrastructure', 'Security', 'Log Management', 'Synthetics & Testing', 'Platform'];

export default function HomePage() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeCategory, setActiveCategory] = useState('All');
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
          catalog: { product_count: data.length, categories, category_count: categories.length, elapsed_ms: elapsed },
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

  const filtered = activeCategory === 'All' ? products : products.filter(p => p.category === activeCategory);

  return (
    <div>
      {q ? (
        /* Search results header */
        <div className="mb-6">
          <div className="text-xl font-semibold text-gray-900">
            Results for <span className="text-[#632ca6]">"{q}"</span>
          </div>
          <div className="text-sm text-gray-400 mt-0.5">{products.length} product{products.length !== 1 ? 's' : ''} found</div>
        </div>
      ) : (
        /* Hero */
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-1.5">
            {/* div not h1 — avoids global h1 styles */}
            <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#111827', lineHeight: 1.25, letterSpacing: '-0.02em' }}>
              DD Store
            </div>
            <span className="text-[11px] font-semibold bg-[#632ca6] text-white px-2 py-0.5 rounded-full tracking-wide">DEMO</span>
          </div>
          <p className="text-gray-500 text-sm">Observability products, fully instrumented with Datadog.</p>

          {/* Category filter */}
          <div className="flex items-center gap-1.5 mt-5 flex-wrap">
            {CATEGORIES.map(cat => (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                className={`text-xs font-medium px-3 py-1.5 rounded-full border transition-all ${
                  activeCategory === cat
                    ? 'bg-[#632ca6] text-white border-[#632ca6]'
                    : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Skeleton */}
      {loading && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-100 overflow-hidden animate-pulse">
              <div className="aspect-[5/3] bg-gray-100" />
              <div className="p-4 space-y-2.5">
                <div className="h-3 bg-gray-100 rounded-full w-1/3" />
                <div className="h-4 bg-gray-100 rounded w-3/4" />
                <div className="h-3 bg-gray-100 rounded w-full" />
                <div className="h-3 bg-gray-100 rounded w-2/3" />
                <div className="h-8 bg-gray-100 rounded-lg mt-3" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-5 flex items-start gap-3">
          <svg className="w-5 h-5 mt-0.5 shrink-0 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div>
            <div className="font-semibold text-sm">Failed to load products</div>
            <div className="text-sm text-red-600 mt-0.5">{error}</div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && filtered.length === 0 && (
        <div className="text-center py-20">
          <div className="w-12 h-12 rounded-2xl bg-gray-100 flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
          </div>
          <div className="text-sm font-medium text-gray-600 mb-1">No products found</div>
          <div className="text-xs text-gray-400">Try a different category or search term</div>
        </div>
      )}

      {/* Grid */}
      {!loading && !error && filtered.length > 0 && (
        <>
          {!q && activeCategory !== 'All' && (
            <div className="text-xs text-gray-400 mb-4">{filtered.length} product{filtered.length !== 1 ? 's' : ''} in {activeCategory}</div>
          )}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {filtered.map(p => (
              <ProductCard key={p.id} product={p} onAdded={load} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
