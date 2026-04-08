const BASE = '/api';

// Persistent session ID for this browser tab
export const SESSION_ID = `sess-${Math.random().toString(36).slice(2, 10)}`;

const headers = () => ({
  'Content-Type': 'application/json',
  'X-Session-Id': SESSION_ID,
});

export const api = {
  getProducts: () =>
    fetch(`${BASE}/products`, { headers: headers() }).then(r => r.json()),

  getProduct: (id) =>
    fetch(`${BASE}/products/${id}`, { headers: headers() }).then(r => {
      if (!r.ok) throw new Error(`Product ${id} not found`);
      return r.json();
    }),

  searchProducts: (q) =>
    fetch(`${BASE}/search?q=${encodeURIComponent(q)}`, { headers: headers() }).then(r => r.json()),

  getRecommendations: () =>
    fetch(`${BASE}/recommendations`, { headers: headers() }).then(r => r.json()),

  getCart: () =>
    fetch(`${BASE}/cart`, { headers: headers() }).then(r => r.json()),

  addToCart: (product_id, quantity = 1) =>
    fetch(`${BASE}/cart`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ product_id, quantity }),
    }).then(r => r.json()),

  clearCart: () =>
    fetch(`${BASE}/cart`, { method: 'DELETE', headers: headers() }).then(r => r.json()),

  checkout: (email) =>
    fetch(`${BASE}/checkout`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ email }),
    }).then(async r => {
      const data = await r.json();
      if (!r.ok) throw Object.assign(new Error(data.error || 'Checkout failed'), { data, status: r.status });
      return data;
    }),

  getOrders: () =>
    fetch(`${BASE}/orders`, { headers: headers() }).then(r => r.json()),

  getStats: () =>
    fetch(`${BASE}/stats`, { headers: headers() }).then(r => r.json()),

  getCategories: () =>
    fetch(`${BASE}/categories`, { headers: headers() }).then(r => r.json()),

  computePrimes: (n = 50000) =>
    fetch(`${BASE}/compute?n=${n}`, { headers: headers() }).then(r => r.json()),
};
