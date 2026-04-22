import { Link } from 'react-router-dom';
import { api } from '../api';
import { logger } from '../datadog';

const CATEGORY_META = {
  'Observability':       { color: '#632ca6', bg: '#f5f3ff' },
  'Infrastructure':      { color: '#0891b2', bg: '#ecfeff' },
  'Security':            { color: '#dc2626', bg: '#fef2f2' },
  'Log Management':      { color: '#16a34a', bg: '#f0fdf4' },
  'Synthetics & Testing':{ color: '#d97706', bg: '#fffbeb' },
  'Platform':            { color: '#475569', bg: '#f8fafc' },
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

  const meta = CATEGORY_META[product.category] || { color: '#632ca6', bg: '#f5f3ff' };
  const accent = product.image_url || meta.color;
  const initials = product.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  const isFree = product.price === 0;

  return (
    <Link
      to={`/product/${product.id}`}
      className="group block bg-white rounded-xl border border-gray-100 overflow-hidden hover:border-gray-200 hover:-translate-y-0.5 transition-all duration-200"
      style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)', ['--hover-shadow']: '0 6px 20px rgba(0,0,0,0.09)' }}
      onMouseEnter={e => e.currentTarget.style.boxShadow = '0 6px 20px rgba(0,0,0,0.09)'}
      onMouseLeave={e => e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.05)'}
    >
      {/* Thumbnail */}
      <div
        className="aspect-[5/3] flex items-center justify-center relative"
        style={{ background: `linear-gradient(145deg, ${accent}18, ${accent}30)` }}
      >
        <div
          className="w-16 h-16 rounded-2xl flex items-center justify-center"
          style={{ background: `linear-gradient(135deg, ${accent}, ${accent}cc)` }}
        >
          <span className="text-white font-bold text-lg tracking-wide">{initials}</span>
        </div>
        {product.stock < 10 && (
          <span className="absolute top-2.5 right-2.5 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200">
            Low stock
          </span>
        )}
      </div>

      {/* Content */}
      <div className="p-4">
        <span
          className="inline-block text-[11px] font-semibold px-2 py-0.5 rounded-md mb-2"
          style={{ color: meta.color, background: meta.bg }}
        >
          {product.category || 'Uncategorized'}
        </span>
        <h3 className="font-semibold text-gray-900 text-sm leading-snug mb-1.5 line-clamp-2">{product.name}</h3>
        <p className="text-xs text-gray-400 line-clamp-2 mb-4 leading-relaxed">
          {product.description_preview || product.description || 'Contact us for pricing.'}
        </p>

        <div className="flex items-center justify-between">
          <div>
            {isFree ? (
              <span className="text-sm font-bold text-emerald-600">Included</span>
            ) : (
              <div className="flex items-baseline gap-1">
                <span className="text-base font-bold text-gray-900">${product.price?.toFixed(2)}</span>
                <span className="text-[11px] text-gray-400">/host/mo</span>
              </div>
            )}
          </div>
          <button
            onClick={handleAdd}
            className="text-[12px] font-semibold px-3 py-1.5 rounded-lg text-white transition-opacity hover:opacity-85 active:opacity-70"
            style={{ background: `linear-gradient(135deg, ${accent}, ${accent}dd)` }}
          >
            Add to plan
          </button>
        </div>
      </div>
    </Link>
  );
}
