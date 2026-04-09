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

    // Load recommendations (intentionally slow endpoint)
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
    <div className="animate-pulse space-y-4">
      <div className="h-8 bg-gray-200 rounded w-1/2" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="aspect-square bg-gray-200 rounded-xl" />
        <div className="space-y-3">
          <div className="h-6 bg-gray-200 rounded w-3/4" />
          <div className="h-4 bg-gray-200 rounded" />
          <div className="h-4 bg-gray-200 rounded w-2/3" />
          <div className="h-12 bg-gray-200 rounded-xl mt-6" />
        </div>
      </div>
    </div>
  );

  if (error) return (
    <div className="bg-red-50 border border-red-200 rounded-xl p-8 text-center">
      <div className="text-4xl mb-3">💥</div>
      <h2 className="text-xl font-bold text-red-700 mb-2">Something went wrong</h2>
      <p className="text-red-600 mb-4">{error}</p>
      <button onClick={() => navigate('/')} className="bg-red-600 text-white px-4 py-2 rounded-lg">
        Back to shop
      </button>
    </div>
  );

  // BUG: WebSocket-based real-time price feed crashes on certain products
  // Simulates a broken SSE/WebSocket handler for live pricing updates
  if (product.id % 5 === 0) {
    const initPriceFeed = (productId) => {
      const parsePriceUpdate = (eventData) => {
        // Simulates receiving malformed SSE event from price feed
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
  // Simulates a heavy client-side tracking library blocking the main thread
  if (product.id % 7 === 0) {
    const start = performance.now();
    while (performance.now() - start < 120) {} // 120ms blocking → Long Task
    window.__leakedProductViews = window.__leakedProductViews || [];
    window.__leakedProductViews.push({ id: product.id, ts: Date.now(), data: new Array(10000).fill('x') });
  }

  return (
    <div>
      <button onClick={() => navigate(-1)} className="text-sm text-gray-500 hover:text-purple-600 mb-6 flex items-center gap-1">
        ← Back
      </button>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
        <div className="rounded-xl overflow-hidden bg-gray-100 aspect-square">
          <img src={product.image_url} alt={product.name} className="w-full h-full object-cover" />
        </div>

        <div className="flex flex-col">
          <div className="text-sm text-purple-600 font-medium mb-2">{product.category || 'Uncategorized'}</div>
          <h1 className="text-2xl font-bold text-gray-900 mb-3">{product.name}</h1>
          <p className="text-gray-600 text-sm leading-relaxed mb-4">{product.description || 'No description available.'}</p>

          <div className="mt-auto">
            <div className="text-3xl font-bold text-gray-900 mb-2">${product.price?.toFixed(2)}</div>
            {product.stock < 10 && (
              <p className="text-sm text-red-500 mb-3">⚠️ Only {product.stock} left in stock</p>
            )}
            <button
              onClick={handleAdd}
              className={`w-full py-3 px-6 rounded-xl font-semibold text-white transition-all ${
                added ? 'bg-green-500' : 'bg-purple-600 hover:bg-purple-700'
              }`}
            >
              {added ? '✓ Added to cart!' : 'Add to cart'}
            </button>
            <button
              onClick={() => { handleAdd(); navigate('/checkout'); }}
              className="w-full mt-2 py-3 px-6 rounded-xl font-semibold border border-purple-600 text-purple-600 hover:bg-purple-50 transition-colors"
            >
              Buy now
            </button>
          </div>
        </div>
      </div>

      <div>
        <h2 className="text-xl font-bold text-gray-900 mb-4">You might also like</h2>
        {recsLoading ? (
          <div className="flex gap-2 items-center text-gray-400 text-sm">
            <div className="w-4 h-4 border-2 border-purple-400 border-t-transparent rounded-full animate-spin" />
            Loading recommendations…
          </div>
        ) : (
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
