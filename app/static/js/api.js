/**
 * CoffeePOS - Cliente API REST Centralizado
 * Gestiona todas las llamadas HTTP al backend FastAPI con manejo de errores y tipado JSON.
 */

const API = {
  // Configuración
  async getConfig() {
    const res = await fetch('/api/configuracion');
    if (!res.ok) throw new Error('Error al cargar configuración');
    return await res.json();
  },

  async updateConfig(data) {
    const res = await fetch('/api/configuracion', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Error al actualizar configuración');
    return await res.json();
  },

  // Productos e Inventario
  async getProducts(busqueda = '', soloActivos = true) {
    const params = new URLSearchParams({ solo_activos: soloActivos });
    if (busqueda.trim()) params.append('busqueda', busqueda.trim());
    const res = await fetch(`/api/productos?${params.toString()}`);
    if (!res.ok) throw new Error('Error al obtener productos');
    return await res.json();
  },

  async createProduct(data) {
    const res = await fetch('/api/productos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (res.status === 409) {
      const err = await res.json();
      throw new Error(err.detail || 'El código de producto ya existe');
    }
    if (!res.ok) throw new Error('Error al crear producto');
    return await res.json();
  },

  async updateProduct(id, data) {
    const res = await fetch(`/api/productos/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (res.status === 409) {
      const err = await res.json();
      throw new Error(err.detail || 'El código de producto ya está en uso');
    }
    if (!res.ok) throw new Error('Error al modificar producto');
    return await res.json();
  },

  async deleteProduct(id) {
    const res = await fetch(`/api/productos/${id}`, {
      method: 'DELETE'
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Error al eliminar producto');
    }
    return await res.json();
  },

  async replenishProduct(id, cantidad) {
    const res = await fetch(`/api/productos/${id}/reabastecer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cantidad: parseInt(cantidad, 10) })
    });
    if (!res.ok) throw new Error('Error al reabastecer producto');
    return await res.json();
  },

  // Pedidos y Checkout Atómico
  async checkout(pedidoData) {
    const res = await fetch('/api/pedidos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(pedidoData)
    });

    if (res.status === 409) {
      const err = await res.json();
      const detalle = err.detail || {};
      throw new Error(detalle.mensaje || 'Stock insuficiente para procesar el pedido.');
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Error en el cobro del pedido.');
    }

    return await res.json();
  },

  async getOrder(id) {
    const res = await fetch(`/api/pedidos/${id}`);
    if (!res.ok) throw new Error('Pedido no encontrado');
    return await res.json();
  },

  // Cierre de Caja & Reportes
  async getDailySummary(fecha = '') {
    const params = fecha ? `?fecha=${fecha}` : '';
    const res = await fetch(`/api/caja/resumen-diario${params}`);
    if (!res.ok) throw new Error('Error al consultar balance diario');
    return await res.json();
  },

  async closeRegister(fecha = '') {
    const params = fecha ? `?fecha=${fecha}` : '';
    const res = await fetch(`/api/caja/cerrar${params}`, { method: 'POST' });
    if (!res.ok) throw new Error('Error al ejecutar cierre de caja');
    return await res.json();
  },

  // Mantenimiento
  async resetStock() {
    const res = await fetch('/api/sistema/reiniciar-stock', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirmar: true })
    });
    if (!res.ok) throw new Error('Error al reiniciar stock');
    return await res.json();
  },

  async wipeDatabase(palabraClave) {
    const res = await fetch('/api/sistema/limpieza-total', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ palabra_clave: palabraClave })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Error al ejecutar restauración');
    }
    return await res.json();
  },

  async loadDemoSeeds() {
    const res = await fetch('/api/sistema/cargar-demo', {
      method: 'POST'
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Error al cargar catálogo demo');
    }
    return await res.json();
  }
};
