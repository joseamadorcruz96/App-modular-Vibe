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

  async getAuditReport(fecha = '') {
    const params = fecha ? `?fecha=${fecha}` : '';
    const res = await fetch(`/api/caja/auditoria-jornada${params}`);
    if (!res.ok) throw new Error('Error al consultar auditoría de ventas');
    return await res.json();
  },

  getDownloadAuditReportUrl(fecha = '') {
    const params = fecha ? `?fecha=${fecha}` : '';
    return `/api/caja/descargar-informe-md${params}`;
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
  },

  // ============================================================================
  // Insumos / Materias Primas
  // ============================================================================
  async getInsumos(soloActivos = true) {
    const res = await fetch(`/api/insumos?solo_activos=${soloActivos}`);
    if (!res.ok) throw new Error('Error al obtener materias primas');
    return await res.json();
  },

  async createInsumo(data) {
    const res = await fetch('/api/insumos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (res.status === 409) {
      const err = await res.json();
      throw new Error(err.detail || 'El código de insumo ya existe');
    }
    if (!res.ok) throw new Error('Error al crear insumo');
    return await res.json();
  },

  async updateInsumo(id, data) {
    const res = await fetch(`/api/insumos/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Error al modificar insumo');
    return await res.json();
  },

  async replenishInsumo(id, cantidad) {
    const res = await fetch(`/api/insumos/${id}/reabastecer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cantidad: parseFloat(cantidad) })
    });
    if (!res.ok) throw new Error('Error al reabastecer insumo');
    return await res.json();
  },

  async deleteInsumo(id, forzar = false) {
    const url = forzar ? `/api/insumos/${id}?forzar=true` : `/api/insumos/${id}`;
    const res = await fetch(url, { method: 'DELETE' });
    if (!res.ok) throw new Error('Error al eliminar insumo');
    return await res.json();
  },

  // ============================================================================
  // Recetas / Escandallos
  // ============================================================================
  async getProductRecipe(productoId) {
    const res = await fetch(`/api/productos/${productoId}/receta`);
    if (!res.ok) throw new Error('Error al consultar receta del producto');
    return await res.json();
  },

  async saveProductRecipe(productoId, ingredientes) {
    const res = await fetch(`/api/productos/${productoId}/receta`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ingredientes })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Error al guardar la receta');
    }
    return await res.json();
  },

  async deleteProductRecipe(productoId) {
    const res = await fetch(`/api/productos/${productoId}/receta`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Error al eliminar receta');
    return await res.json();
  },

  // ============================================================================
  // Comandas y Mesas Abiertas
  // ============================================================================
  async getMesasEstado() {
    const res = await fetch('/api/comandas/mesas-estado');
    if (!res.ok) throw new Error('Error al obtener estado de mesas');
    return await res.json();
  },

  async getComandaMesa(mesa) {
    const res = await fetch(`/api/comandas/mesa/${encodeURIComponent(mesa)}`);
    if (res.status === 404) return null;
    if (!res.ok) throw new Error('Error al consultar comanda de mesa');
    return await res.json();
  },

  async openComanda(mesa, cliente = 'Consumidor Final') {
    const res = await fetch('/api/comandas/abrir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mesa, cliente })
    });
    if (res.status === 409) {
      const err = await res.json();
      throw new Error(err.detail || 'La mesa ya se encuentra ocupada');
    }
    if (!res.ok) throw new Error('Error al abrir comanda en mesa');
    return await res.json();
  },

  async addComandaItems(comandaId, items) {
    const res = await fetch(`/api/comandas/${comandaId}/items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items })
    });
    if (!res.ok) throw new Error('Error al agregar productos a la mesa');
    return await res.json();
  },

  async serveComanda(comandaId) {
    const res = await fetch(`/api/comandas/${comandaId}/servir`, { method: 'POST' });
    if (res.status === 409) {
      const err = await res.json();
      throw new Error(err.detail || 'Stock insuficiente para servir todos los productos.');
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Error al marcar comanda como servida');
    }
    return await res.json();
  },

  async serveComandaItem(comandaId, detalleId) {
    const res = await fetch(`/api/comandas/${comandaId}/items/${detalleId}/servir`, { method: 'POST' });
    if (res.status === 409) {
      const err = await res.json();
      throw new Error(err.detail || 'Stock insuficiente para servir este producto.');
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Error al marcar ítem como servido');
    }
    return await res.json();
  },

  async removeComandaItem(comandaId, detalleId, restaurarStock = false) {
    const res = await fetch(`/api/comandas/${comandaId}/items/${detalleId}?restaurar_stock=${restaurarStock}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Error al remover producto de la comanda');
    return await res.json();
  },

  async checkoutComanda(comandaId, checkoutData) {
    const res = await fetch(`/api/comandas/${comandaId}/checkout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(checkoutData)
    });
    if (res.status === 409) {
      const err = await res.json();
      throw new Error(err.detail || 'Stock insuficiente para liquidar la mesa.');
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Error al liquidar comanda de mesa');
    }
    return await res.json();
  },

  async cancelComanda(comandaId, restaurarStock = false) {
    const res = await fetch(`/api/comandas/${comandaId}/cancelar?restaurar_stock=${restaurarStock}`, { method: 'POST' });
    if (!res.ok) throw new Error('Error al cancelar comanda');
    return await res.json();
  }
};

