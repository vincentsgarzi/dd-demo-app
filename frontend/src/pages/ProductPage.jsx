import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api';
import { logger } from '../datadog';
import ProductCard from '../components/ProductCard';

export default function ProductPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [product, setProduct] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [recsLoading, setRecsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [added, setAdded] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const start = performance.now();

    logger.info(`Viewing product #${id}`, { product: { id: Number(id) }, action: 'product_page_opened' });

    api.getProduct(Number(id))
      .then(p => {
        const elapsed = Math.round(performance.now() - start);
        logger.info(`Product loaded — "${p.name}" ($${p.price?.toFixed(2)}, ${p.stock} in stock) in ${elapsed}ms`, {
          product: { id: p.id, name: p.name, price: p.price, stock: p.stock, category: p.category },
          elapsed_ms: elapsed,
          action: 'product_loaded',
        });
        if (p.stock < 10) {
          logger.warn(`Low stock on "${p.name}" — only ${p.stock} remaining`, {
            product: { id: p.id, name: p.name, stock: p.stock },
            action: 'low_stock_viewed',
          });
        }
        setProduct(p);
      })
      .catch(err => {
        logger.error(`Failed to load product #${id}: ${err.message}`, {
          product: { id: Number(id) },
          error: { message: err.message },
          action: 'product_load_failed',
        });
        setError(err.message);
      })
      .finally(() => setLoading(false));

    setRecsLoading(true);
    const recsStart = performance.now();
    logger.info('Fetching recommendations (slow endpoint)', { action: 'recommendations_requested' });

    api.getRecommendations()
      .then(recs => {
        const elapsed = Math.round(performance.now() - recsStart);
        const names = recs.map(r => r.name);
        logger.info(`Recommendations loaded — ${recs.length} products in ${elapsed}ms`, {
          recommendations: { count: recs.length, product_names: names, elapsed_ms: elapsed },
          action: 'recommendations_loaded',
        });
        if (elapsed > 2000) {
          logger.warn(`Recommendation engine is slow — ${elapsed}ms to fetch ${recs.length} products`, {
            recommendations: { elapsed_ms: elapsed },
            action: 'recommendations_slow',
          });
        }
        setRecommendations(recs);
      })
      .catch(() => setRecommendations([]))
      .finally(() => setRecsLoading(false));
  }, [id]);

  const handleAdd = async () => {
    try {
      await api.addToCart(product.id);
      setAdded(true);
      logger.info(`Added "${product.name}" to cart ($${product.price?.toFixed(2)})`, {
        product: { id: product.id, name: product.name, price: product.price },
        action: 'add_to_cart_success',
      });
      setTimeout(() => setAdded(false), 2000);
    } catch (err) {
      logger.error(`Add to cart failed for "${product?.name || id}": ${err.message}`, {
        product: { id: Number(id), name: product?.name },
        error: { message: err.message },
        action: 'add_to_cart_failed',
      });
    }
  };

  if (loading) return (
    <div className="animate-pulse">
      <div className="h-5 bg-gray-100 rounded w-48 mb-8" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
        <div className="aspect-square bg-gray-100 rounded-2xl" />
        <div className="space-y-4 py-2">
          <div className="h-3 bg-gray-100 rounded w-24" />
          <div className="h-7 bg-gray-100 rounded w-3/4" />
          <div className="h-4 bg-gray-100 rounded" />
          <div className="h-4 bg-gray-100 rounded w-5/6" />
          <div className="h-4 bg-gray-100 rounded w-2/3" />
          <div className="h-12 bg-gray-100 rounded-xl mt-8" />
          <div className="h-12 bg-gray-100 rounded-xl" />
        </div>
      </div>
    </div>
  );

  if (error) return (
    <div className="bg-white border border-red-100 rounded-2xl p-10 text-center">
      <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-4">
        <svg className="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      </div>
      <h2 className="text-base font-semibold text-gray-900 mb-1">Failed to load product</h2>
      <p className="text-sm text-gray-500 mb-6">{error}</p>
      <button onClick={() => navigate('/')} className="px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800">
        Back to shop
      </button>
    </div>
  );

  // BUG: WebSocket-based real-time price feed crashes on certain products
  if (product.id % 5 === 0) {
    const initPriceFeed = (productId) => {
      const parsePriceUpdate = (eventData) => {
        const update = JSON.parse(eventData);
        return update.pricing.realtime.bid_ask_spread.toFixed(4);
      };
      return parsePriceUpdate('{"type":"price_update","product_id":' + productId + '}');
    };
    try {
      initPriceFeed(product.id);
    } catch (e) {
      throw new Error(
        `PriceFeedError: real-time pricing WebSocket returned malformed event for ` +
        `product_id=${product.id} ("${product.name}"). ` +
        `Field 'pricing.realtime.bid_ask_spread' is undefined — ` +
        `price feed schema v2.3 does not include real-time fields for this product tier. ` +
        `${Math.floor(Math.random() * 200 + 50)} other sessions affected. ` +
        `Fallback to cached price: $${product.price?.toFixed(2)}`
      );
    }
  }

  // BUG: Third-party analytics SDK causes long task + memory leak
  if (product.id % 7 === 0) {
    const start = performance.now();
    while (performance.now() - start < 120) {}
    window.__leakedProductViews = window.__leakedProductViews || [];
    window.__leakedProductViews.push({ id: product.id, ts: Date.now(), data: new Array(10000).fill('x') });
  }

  const accent = product.image_url || '#632ca6';
  const initials = product.name.split(' ').map(w => w[0]).join('').slice(0, 3).toUpperCase();

  return (
    <div>
      {/* Back nav */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-700 mb-8 transition-colors group"
      >
        <svg className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back
      </button>

      {/* Product detail */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-10 mb-16">
        {/* Image */}
        <div
          className="rounded-2xl overflow-hidden aspect-square flex items-center justify-center"
          style={{ background: `linear-gradient(145deg, ${accent}18, ${accent}35)` }}
        >
          <div className="w-28 h-28 rounded-3xl flex items-center justify-center" style={{ background: `linear-gradient(135deg, ${accent}, ${accent}cc)` }}>
            <span className="text-white font-bold text-3xl tracking-wider">{initials}</span>
          </div>
        </div>

        {/* Info */}
        <div className="flex flex-col py-1">
          <div className="text-xs font-semibold mb-3 px-2.5 py-1 rounded-md inline-block self-start" style={{ color: accent, background: `${accent}15` }}>
            {product.category || 'Uncategorized'}
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-3 leading-snug">{product.name}</h1>
          <p className="text-gray-500 text-sm leading-relaxed mb-6">{product.description || 'No description available.'}</p>

          <div className="mt-auto space-y-3">
            {/* Price */}
            <div className="flex items-baseline gap-2">
              {product.price === 0 ? (
                <span className="text-2xl font-bold text-emerald-600">Included with Enterprise</span>
              ) : (
                <>
                  <span className="text-3xl font-bold text-gray-900">${product.price?.toFixed(2)}</span>
                  <span className="text-sm text-gray-400">/host/month</span>
                </>
              )}
            </div>

            {/* Stock warning */}
            {product.stock < 10 && (
              <div className="flex items-center gap-1.5 text-sm text-amber-600">
                <span className="w-1.5 h-1.5 bg-amber-500 rounded-full" />
                Only {product.stock} licenses remaining
              </div>
            )}

            {/* CTAs */}
            <button
              onClick={handleAdd}
              className={`w-full py-3 px-6 rounded-xl font-semibold text-white text-sm transition-all ${
                added ? 'bg-emerald-500' : 'hover:opacity-90 active:scale-[0.99]'
              }`}
              style={!added ? { background: `linear-gradient(135deg, ${accent}, ${accent}dd)` } : {}}
            >
              {added ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                  Added to plan
                </span>
              ) : 'Add to plan'}
            </button>
            <button
              onClick={() => { handleAdd(); navigate('/checkout'); }}
              className="w-full py-3 px-6 rounded-xl font-semibold text-sm border-2 transition-colors hover:bg-gray-50"
              style={{ borderColor: accent, color: accent }}
            >
              Subscribe now →
            </button>
          </div>
        </div>
      </div>

      {/* Recommendations */}
      <div>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-gray-900">You might also like</h2>
          {recsLoading && (
            <div className="flex items-center gap-2 text-xs text-gray-400">
              <div className="w-3.5 h-3.5 border-2 border-purple-400 border-t-transparent rounded-full animate-spin" />
              Loading…
            </div>
          )}
        </div>
        {!recsLoading && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {recommendations.filter(r => r.id !== product.id).slice(0, 4).map(p => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
