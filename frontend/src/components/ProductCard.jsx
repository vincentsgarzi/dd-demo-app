import { Link } from 'react-router-dom';
import { api } from '../api';
import { logger } from '../datadog';

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

  const isPerUnit = product.price < 5;

  return (
    <Link to={`/product/${product.id}`} className="group block bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden hover:shadow-md transition-shadow">
      <div className="aspect-[4/3] bg-gray-100 overflow-hidden">
        <img
          src={product.image_url}
          alt={product.name}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          loading="lazy"
        />
      </div>
      <div className="p-4">
        <div className="text-xs text-[#632ca6] font-medium mb-1">{product.category || 'Uncategorized'}</div>
        <h3 className="font-semibold text-gray-900 text-sm leading-tight mb-1 line-clamp-2">{product.name}</h3>
        <p className="text-xs text-gray-500 line-clamp-2 mb-3">{product.description_preview || product.description || '—'}</p>
        <div className="flex items-center justify-between">
          <div>
            <span className="text-lg font-bold text-gray-900">${product.price?.toFixed(2)}</span>
            <span className="text-xs text-gray-400 ml-1">{isPerUnit ? '/unit' : '/mo'}</span>
          </div>
          <button
            onClick={handleAdd}
            className="bg-[#632ca6] hover:bg-[#4e1f8a] text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
          >
            Add to plan
          </button>
        </div>
        {product.stock < 10 && (
          <p className="text-xs text-red-500 mt-1">Only {product.stock} licenses left!</p>
        )}
      </div>
    </Link>
  );
}
