import { Link } from 'react-router-dom';
import { api } from '../api';
import { logger } from '../datadog';

const CATEGORY_ICONS = {
  'Observability': '📊',
  'Infrastructure': '🖥️',
  'Security': '🔒',
  'Log Management': '📝',
  'Synthetics & Testing': '🧪',
  'Platform': '⚙️',
};

export default function ProductCard({ product, onAdded }) {
  const handleAdd = async (e) => {
    e.preventDefault();
    try {
      await api.addToCart(product.id);
      logger.info('Product added to cart', { product_id: product.id, product_name: product.name });
      if (onAdded) onAdded();
    } catch (err) {
      logger.error('Failed to add to cart', { error: err.message, product_id: product.id });
    }
  };

  const color = product.image_url || '#632ca6';
  const icon = CATEGORY_ICONS[product.category] || '📦';
  const initials = product.name.split(' ').map(w => w[0]).join('').slice(0, 3).toUpperCase();
  const isFree = product.price === 0;

  return (
    <Link to={`/product/${product.id}`} className="group block bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200">
      <div
        className="aspect-[5/3] flex items-center justify-center relative overflow-hidden"
        style={{ background: `linear-gradient(135deg, ${color}, ${color}dd)` }}
      >
        <span className="text-white/20 text-6xl font-black select-none">{initials}</span>
        <span className="absolute top-3 left-3 text-xl">{icon}</span>
      </div>
      <div className="p-4">
        <div className="text-xs font-medium mb-1.5" style={{ color }}>{product.category || 'Uncategorized'}</div>
        <h3 className="font-semibold text-gray-900 text-sm leading-tight mb-1 line-clamp-2">{product.name}</h3>
        <p className="text-xs text-gray-500 line-clamp-2 mb-3">{product.description_preview || product.description || 'Configuration required.'}</p>
        <div className="flex items-center justify-between">
          <div>
            {isFree ? (
              <span className="text-lg font-bold text-green-600">Included</span>
            ) : (
              <>
                <span className="text-lg font-bold text-gray-900">${product.price?.toFixed(2)}</span>
                <span className="text-xs text-gray-400 ml-1">/host/mo</span>
              </>
            )}
          </div>
          <button
            onClick={handleAdd}
            className="text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
            style={{ backgroundColor: color }}
          >
            Add to plan
          </button>
        </div>
        {product.stock < 10 && (
          <p className="text-xs text-amber-600 mt-2 flex items-center gap-1">
            <span className="w-1.5 h-1.5 bg-amber-500 rounded-full inline-block" />
            Only {product.stock} licenses left
          </p>
        )}
      </div>
    </Link>
  );
}
