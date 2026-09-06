/**
 * CoffeePOS - Módulo de Inventario & Reabastecimiento
 * Permite visualizar el catálogo, detectar stock crítico (<= 5), dar de alta productos,
 * modificar cualquier atributo, reabastecer unidades y eliminar productos de forma segura.
 */

window.Inventario = {
  productos: [],
  reabastecerProductoSeleccionado: null,
  editarProductoSeleccionado: null,

  async init() {
    this.bindEvents();
    await this.load();
  },

  bindEvents() {
    // Buscador en inventario
    const searchInput = document.getElementById('inv-search');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => this.renderTable(e.target.value));
    }

    // Modal Crear Producto
    const btnNewProduct = document.getElementById('btn-open-new-product');
    if (btnNewProduct) {
      btnNewProduct.addEventListener('click', () => this.openNewProductModal());
    }

    const formNewProduct = document.getElementById('form-new-product');
    if (formNewProduct) {
      formNewProduct.addEventListener('submit', (e) => this.handleCreateProduct(e));
    }

    // Modal Editar Producto
    const formEditProduct = document.getElementById('form-edit-product');
    if (formEditProduct) {
      formEditProduct.addEventListener('submit', (e) => this.handleEditProduct(e));
    }

    // Formulario Reabastecer Rápido
    const formReplenish = document.getElementById('form-replenish-product');
    if (formReplenish) {
      formReplenish.addEventListener('submit', (e) => this.handleReplenish(e));
    }
  },

  async load() {
    try {
      this.productos = await API.getProducts('', false);
      this.renderTable();
    } catch (err) {
      App.showToast('Error cargando inventario', 'error');
    }
  },

  renderTable(filtro = '') {
    const tbody = document.getElementById('inv-table-body');
    if (!tbody) return;

    const term = filtro.toLowerCase().trim();
    const filtrados = this.productos.filter(p =>
      p.nombre.toLowerCase().includes(term) || p.codigo.toLowerCase().includes(term)
    );

    if (filtrados.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align: center; padding: 2rem; color: var(--text-dim);">
            No se encontraron productos en el inventario.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = filtrados.map(prod => {
      const isCritical = prod.stock_actual <= 5;
      const stockBadge = isCritical
        ? `<span class="stock-indicator critical">🚨 ${prod.stock_actual} (Crítico)</span>`
        : `<span class="stock-indicator ok">✓ ${prod.stock_actual}</span>`;

      // Escapar comillas para JSON seguro
      const prodJson = JSON.stringify(prod).replace(/"/g, '&quot;');

      return `
        <tr>
          <td style="font-family: var(--font-mono); font-weight: 700;">${prod.codigo}</td>
          <td style="font-weight: 600;">${prod.nombre}</td>
          <td style="font-family: var(--font-mono); color: var(--text-muted);">${prod.stock_inicial}</td>
          <td>${stockBadge}</td>
          <td style="font-family: var(--font-mono);">${App.formatMoney(prod.costo_unitario)}</td>
          <td style="font-family: var(--font-mono); font-weight: 700; color: var(--accent-gold);">${App.formatMoney(prod.precio_venta)}</td>
          <td>
            <span style="font-size: 0.75rem; padding: 0.2rem 0.5rem; border-radius: var(--radius-full); ${prod.activo ? 'background: rgba(16,185,129,0.1); color: var(--success);' : 'background: rgba(239,68,68,0.1); color: var(--danger);'}">
              ${prod.activo ? 'Activo' : 'Inactivo'}
            </span>
          </td>
          <td>
            <div style="display: flex; gap: 0.4rem; align-items: center; flex-wrap: nowrap;">
              <button class="table-pill-btn" style="padding: 0.35rem 0.65rem; font-size: 0.75rem; min-height: 32px;"
                      onclick="Inventario.openEditModal(${prodJson})" title="Modificar Producto">
                ✏️ Editar
              </button>
              <button class="table-pill-btn" style="padding: 0.35rem 0.65rem; font-size: 0.75rem; min-height: 32px;"
                      onclick="Inventario.openReplenishModal(${prod.id}, '${prod.nombre.replace(/'/g, "\\'")}', ${prod.stock_actual})" title="Sumar Stock">
                ➕ Stock
              </button>
              <button class="table-pill-btn" style="padding: 0.35rem 0.65rem; font-size: 0.75rem; min-height: 32px; border-color: rgba(239,68,68,0.3); color: var(--danger);"
                      onclick="Inventario.handleDeleteProduct(${prod.id}, '${prod.nombre.replace(/'/g, "\\'")}')" title="Eliminar Producto">
                🗑️ Borrar
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  },

  // ==========================================
  // Creación de Producto
  // ==========================================
  openNewProductModal() {
    document.getElementById('form-new-product').reset();
    document.getElementById('modal-new-product').classList.add('active');
  },

  closeNewProductModal() {
    document.getElementById('modal-new-product').classList.remove('active');
  },

  async handleCreateProduct(e) {
    e.preventDefault();
    const codigo = document.getElementById('new-prod-codigo').value.trim();
    const nombre = document.getElementById('new-prod-nombre').value.trim();
    const stock_inicial = parseInt(document.getElementById('new-prod-stock').value, 10);
    const costo_unitario = parseFloat(document.getElementById('new-prod-costo').value);
    const precio_venta = parseFloat(document.getElementById('new-prod-precio').value);

    try {
      await API.createProduct({
        codigo,
        nombre,
        stock_inicial,
        costo_unitario,
        precio_venta
      });
      App.showToast(`Producto '${nombre}' creado exitosamente`, 'success');
      this.closeNewProductModal();
      await this.load();
      if (window.TPV) window.TPV.loadProducts();
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  },

  // ==========================================
  // Edición / Modificación de Producto
  // ==========================================
  openEditModal(prod) {
    this.editarProductoSeleccionado = prod.id;
    document.getElementById('edit-prod-id').value = prod.id;
    document.getElementById('edit-prod-codigo').value = prod.codigo;
    document.getElementById('edit-prod-nombre').value = prod.nombre;
    document.getElementById('edit-prod-stock-inicial').value = prod.stock_inicial;
    document.getElementById('edit-prod-stock-actual').value = prod.stock_actual;
    document.getElementById('edit-prod-costo').value = prod.costo_unitario;
    document.getElementById('edit-prod-precio').value = prod.precio_venta;
    document.getElementById('edit-prod-activo').value = String(prod.activo);

    document.getElementById('modal-edit-product').classList.add('active');
  },

  closeEditModal() {
    document.getElementById('modal-edit-product').classList.remove('active');
  },

  async handleEditProduct(e) {
    e.preventDefault();
    if (!this.editarProductoSeleccionado) return;

    const productoId = this.editarProductoSeleccionado;
    const codigo = document.getElementById('edit-prod-codigo').value.trim();
    const nombre = document.getElementById('edit-prod-nombre').value.trim();
    const stock_inicial = parseInt(document.getElementById('edit-prod-stock-inicial').value, 10);
    const stock_actual = parseInt(document.getElementById('edit-prod-stock-actual').value, 10);
    const costo_unitario = parseFloat(document.getElementById('edit-prod-costo').value);
    const precio_venta = parseFloat(document.getElementById('edit-prod-precio').value);
    const activo = parseInt(document.getElementById('edit-prod-activo').value, 10);

    try {
      const prodActualizado = await API.updateProduct(productoId, {
        codigo,
        nombre,
        stock_inicial,
        stock_actual,
        costo_unitario,
        precio_venta,
        activo
      });
      App.showToast(`Producto '${prodActualizado.nombre}' actualizado exitosamente`, 'success');
      this.closeEditModal();
      await this.load();
      if (window.TPV) window.TPV.loadProducts();
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  },

  // ==========================================
  // Eliminación de Producto
  // ==========================================
  async handleDeleteProduct(productoId, productoNombre) {
    const confirmacion = confirm(
      `¿Está seguro de eliminar el producto '${productoNombre}'?\n\n` +
      `• Si no posee ventas registradas, se eliminará definitivamente.\n` +
      `• Si posee ventas históricas en tickets, se desactivará automáticamente para preservar el historial contable.`
    );

    if (!confirmacion) return;

    try {
      const res = await API.deleteProduct(productoId);
      App.showToast(res.mensaje, res.tipo_eliminacion === 'fisica' ? 'success' : 'info');
      await this.load();
      if (window.TPV) window.TPV.loadProducts();
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  },

  // ==========================================
  // Reabastecimiento Rápido
  // ==========================================
  openReplenishModal(id, nombre, stockActual) {
    this.reabastecerProductoSeleccionado = id;
    document.getElementById('replenish-prod-name').textContent = nombre;
    document.getElementById('replenish-prod-stock').textContent = stockActual;
    document.getElementById('replenish-cant-input').value = 10;
    document.getElementById('modal-replenish-product').classList.add('active');
  },

  closeReplenishModal() {
    document.getElementById('modal-replenish-product').classList.remove('active');
  },

  async handleReplenish(e) {
    e.preventDefault();
    if (!this.reabastecerProductoSeleccionado) return;

    const cantidad = parseInt(document.getElementById('replenish-cant-input').value, 10);
    if (isNaN(cantidad) || cantidad <= 0) {
      App.showToast('Ingrese una cantidad válida mayor a cero', 'error');
      return;
    }

    try {
      const prodActualizado = await API.replenishProduct(this.reabastecerProductoSeleccionado, cantidad);
      App.showToast(`Stock actualizado a ${prodActualizado.stock_actual} unidades`, 'success');
      this.closeReplenishModal();
      await this.load();
      if (window.TPV) window.TPV.loadProducts();
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  }
};
