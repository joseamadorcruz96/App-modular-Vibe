/**
 * CoffeePOS - Módulo de Inventario, Insumos & Recetas (Escandallos)
 * Permite visualizar el catálogo de productos terminados y materias primas,
 * formular recetas con cálculo dinámico de costos y márgenes, y reabastecer existencias.
 */

window.Inventario = {
  productos: [],
  insumos: [],
  subTabActual: 'productos',
  reabastecerProductoSeleccionado: null,
  editarProductoSeleccionado: null,

  // Estado de la receta activa en edición
  recetaActual: {
    productoId: null,
    productoNombre: '',
    precioVenta: 0,
    ingredientes: [] // [{ insumo_id, insumo_codigo, insumo_nombre, unidad_medida, cantidad, costo_unitario_insumo, costo_por_porcion }]
  },

  reabastecerInsumoSeleccionado: null,

  async init() {
    this.bindEvents();
    await this.load();
  },

  bindEvents() {
    // Buscador en productos
    const searchInput = document.getElementById('inv-search');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => this.renderProductosTable(e.target.value));
    }

    // Buscador en insumos
    const insumosSearchInput = document.getElementById('insumos-search');
    if (insumosSearchInput) {
      insumosSearchInput.addEventListener('input', (e) => this.renderInsumosTable(e.target.value));
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

    // Formulario Reabastecer Producto
    const formReplenish = document.getElementById('form-replenish-product');
    if (formReplenish) {
      formReplenish.addEventListener('submit', (e) => this.handleReplenish(e));
    }

    // Formulario Nuevo Insumo
    const formNewInsumo = document.getElementById('form-new-insumo');
    if (formNewInsumo) {
      formNewInsumo.addEventListener('submit', (e) => this.handleCreateInsumo(e));
    }

    // Formulario Reabastecer Insumo
    const formReplenishInsumo = document.getElementById('form-replenish-insumo');
    if (formReplenishInsumo) {
      formReplenishInsumo.addEventListener('submit', (e) => this.handleReplenishInsumo(e));
    }
  },

  switchSubTab(tab) {
    this.subTabActual = tab;
    const btnProds = document.getElementById('tab-btn-inv-prods');
    const btnInsumos = document.getElementById('tab-btn-inv-insumos');
    const subProds = document.getElementById('subtab-productos');
    const subInsumos = document.getElementById('subtab-insumos');

    if (tab === 'productos') {
      if (btnProds) btnProds.classList.add('active');
      if (btnInsumos) btnInsumos.classList.remove('active');
      if (subProds) subProds.style.display = 'block';
      if (subInsumos) subInsumos.style.display = 'none';
      this.renderProductosTable();
    } else {
      if (btnProds) btnProds.classList.remove('active');
      if (btnInsumos) btnInsumos.classList.add('active');
      if (subProds) subProds.style.display = 'none';
      if (subInsumos) subInsumos.style.display = 'block';
      this.renderInsumosTable();
    }
  },

  async load() {
    try {
      this.productos = await API.getProducts('', false);
      this.insumos = await API.getInsumos(false);
      this.renderProductosTable();
      this.renderInsumosTable();
    } catch (err) {
      App.showToast('Error cargando inventario e insumos', 'error');
    }
  },

  // ==========================================================================
  // Renderizado de Catálogo de Productos
  // ==========================================================================
  renderProductosTable(filtro = '') {
    const tbody = document.getElementById('inv-table-body');
    if (!tbody) return;

    const term = filtro.toLowerCase().trim();
    const filtrados = this.productos.filter(p =>
      p.nombre.toLowerCase().includes(term) || p.codigo.toLowerCase().includes(term)
    );

    if (filtrados.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="9" style="text-align: center; padding: 2rem; color: var(--text-dim);">
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
            <button class="table-pill-btn" style="padding: 0.25rem 0.6rem; font-size: 0.75rem; border-color: var(--accent-gold); color: var(--accent-gold);"
                    onclick="Inventario.openRecipeModal(${prod.id})" title="Gestionar receta y escandallo">
              🧪 Receta
            </button>
          </td>
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

  // ==========================================================================
  // Renderizado de Tabla de Insumos
  // ==========================================================================
  renderInsumosTable(filtro = '') {
    const tbody = document.getElementById('insumos-table-body');
    if (!tbody) return;

    const term = filtro.toLowerCase().trim();
    const filtrados = this.insumos.filter(i =>
      i.nombre.toLowerCase().includes(term) || i.codigo.toLowerCase().includes(term)
    );

    if (filtrados.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align: center; padding: 2rem; color: var(--text-dim);">
            No se encontraron materias primas en el inventario.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = filtrados.map(ins => {
      const isCritical = ins.stock_actual <= ins.stock_minimo;
      const stockBadge = isCritical
        ? `<span class="stock-indicator critical">🚨 ${ins.stock_actual} ${ins.unidad_medida} (Bajo)</span>`
        : `<span class="stock-indicator ok">✓ ${ins.stock_actual} ${ins.unidad_medida}</span>`;

      return `
        <tr>
          <td style="font-family: var(--font-mono); font-weight: 700;">${ins.codigo}</td>
          <td style="font-weight: 600;">${ins.nombre}</td>
          <td style="color: var(--text-muted); font-size: 0.85rem;">${ins.unidad_medida}</td>
          <td>${stockBadge}</td>
          <td style="font-family: var(--font-mono); color: var(--text-muted);">${ins.stock_minimo} ${ins.unidad_medida}</td>
          <td style="font-family: var(--font-mono); font-weight: 700; color: var(--accent-gold);">${App.formatMoney(ins.costo_unitario)} / ${ins.unidad_medida}</td>
          <td>
            <span style="font-size: 0.75rem; padding: 0.2rem 0.5rem; border-radius: var(--radius-full); ${ins.activo ? 'background: rgba(16,185,129,0.1); color: var(--success);' : 'background: rgba(239,68,68,0.1); color: var(--danger);'}">
              ${ins.activo ? 'Activo' : 'Inactivo'}
            </span>
          </td>
          <td>
            <div style="display: flex; gap: 0.4rem; align-items: center;">
              <button class="table-pill-btn" style="padding: 0.35rem 0.65rem; font-size: 0.75rem; min-height: 32px;"
                      onclick="Inventario.openReplenishInsumoModal(${ins.id}, '${ins.nombre.replace(/'/g, "\\'")}', ${ins.stock_actual}, '${ins.unidad_medida}')" title="Reabastecer">
                ➕ Stock
              </button>
              <button class="table-pill-btn" style="padding: 0.35rem 0.65rem; font-size: 0.75rem; min-height: 32px; border-color: rgba(239,68,68,0.3); color: var(--danger);"
                      onclick="Inventario.handleDeleteInsumo(${ins.id}, '${ins.nombre.replace(/'/g, "\\'")}')" title="Eliminar Insumo">
                🗑️ Borrar
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  },

  // ==========================================================================
  // Modal de Ficha Técnica de Receta & Escandallo
  // ==========================================================================
  async openRecipeModal(productoId) {
    try {
      const receta = await API.getProductRecipe(productoId);
      this.recetaActual = {
        productoId: receta.producto_id,
        productoNombre: receta.producto_nombre,
        precioVenta: receta.precio_venta,
        ingredientes: [...receta.ingredientes]
      };

      document.getElementById('recipe-modal-prod-title').innerHTML = `
        Producto: <strong style="color: #fff;">${receta.producto_nombre}</strong> (${receta.producto_codigo})
      `;

      // Cargar opciones en el select de insumos
      const selectInsumo = document.getElementById('recipe-add-insumo-select');
      if (selectInsumo) {
        selectInsumo.innerHTML = this.insumos
          .filter(i => i.activo)
          .map(i => `<option value="${i.id}" data-unit="${i.unidad_medida}" data-cost="${i.costo_unitario}">${i.nombre} (${i.unidad_medida} - ${App.formatMoney(i.costo_unitario)})</option>`)
          .join('');
      }

      this.updateRecipeMetricsAndTable();
      document.getElementById('modal-recipe-config').classList.add('active');
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  },

  closeRecipeModal() {
    document.getElementById('modal-recipe-config').classList.remove('active');
  },

  updateRecipeMetricsAndTable() {
    const tableBody = document.getElementById('recipe-items-table-body');
    const precioEl = document.getElementById('recipe-metric-precio');
    const costoEl = document.getElementById('recipe-metric-costo');
    const margenDineroEl = document.getElementById('recipe-metric-margen-dinero');
    const margenPctEl = document.getElementById('recipe-metric-margen-pct');
    const btnDelete = document.getElementById('btn-delete-recipe');

    let costoTotal = 0;

    if (this.recetaActual.ingredientes.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align: center; padding: 1.5rem; color: var(--text-dim);">
            Sin receta configurada. Este producto opera con stock unitario directo.
          </td>
        </tr>
      `;
      if (btnDelete) btnDelete.style.display = 'none';
    } else {
      if (btnDelete) btnDelete.style.display = 'inline-block';
      tableBody.innerHTML = this.recetaActual.ingredientes.map((ing, idx) => {
        const costoPorcion = ing.cantidad * ing.costo_unitario_insumo;
        costoTotal += costoPorcion;
        return `
          <tr>
            <td style="font-weight: 600;">${ing.insumo_nombre}</td>
            <td style="font-family: var(--font-mono); font-weight: 700;">${ing.cantidad}</td>
            <td style="color: var(--text-muted);">${ing.unidad_medida}</td>
            <td style="font-family: var(--font-mono); color: var(--accent-gold);">${App.formatMoney(costoPorcion)}</td>
            <td>
              <button class="cart-item-remove" onclick="Inventario.removeIngredientFromRecipeList(${idx})" title="Quitar">✕</button>
            </td>
          </tr>
        `;
      }).join('');
    }

    const precioVenta = this.recetaActual.precioVenta;
    const margenBruto = precioVenta - costoTotal;
    const margenPct = precioVenta > 0 ? (margenBruto / precioVenta * 100) : 0;

    precioEl.textContent = App.formatMoney(precioVenta);
    costoEl.textContent = App.formatMoney(costoTotal);
    margenDineroEl.textContent = App.formatMoney(margenBruto);
    margenPctEl.textContent = `${margenPct.toFixed(1)}%`;

    // Color del margen según rentabilidad
    if (margenPct >= 60) {
      margenPctEl.style.color = '#34d399';
    } else if (margenPct >= 30) {
      margenPctEl.style.color = '#fbbf24';
    } else {
      margenPctEl.style.color = '#f87171';
    }
  },

  addIngredientToRecipeList() {
    const select = document.getElementById('recipe-add-insumo-select');
    const cantInput = document.getElementById('recipe-add-cantidad-input');
    const insumoId = parseInt(select.value, 10);
    const cantidad = parseFloat(cantInput.value);

    if (isNaN(cantidad) || cantidad <= 0) {
      App.showToast('Ingrese una cantidad válida mayor a cero', 'error');
      return;
    }

    const insumoObj = this.insumos.find(i => i.id === insumoId);
    if (!insumoObj) return;

    // Verificar si ya está en la lista
    const existente = this.recetaActual.ingredientes.find(i => i.insumo_id === insumoId);
    if (existente) {
      existente.cantidad += cantidad;
    } else {
      this.recetaActual.ingredientes.push({
        insumo_id: insumoObj.id,
        insumo_codigo: insumoObj.codigo,
        insumo_nombre: insumoObj.nombre,
        unidad_medida: insumoObj.unidad_medida,
        cantidad: cantidad,
        costo_unitario_insumo: insumoObj.costo_unitario,
        costo_por_porcion: cantidad * insumoObj.costo_unitario
      });
    }

    cantInput.value = 10;
    this.updateRecipeMetricsAndTable();
  },

  removeIngredientFromRecipeList(index) {
    this.recetaActual.ingredientes.splice(index, 1);
    this.updateRecipeMetricsAndTable();
  },

  async saveCurrentRecipe() {
    if (this.recetaActual.ingredientes.length === 0) {
      App.showToast('Agregue al menos un insumo a la receta o presione Eliminar Receta.', 'warning');
      return;
    }

    const payload = this.recetaActual.ingredientes.map(i => ({
      insumo_id: i.insumo_id,
      cantidad: i.cantidad
    }));

    try {
      await API.saveProductRecipe(this.recetaActual.productoId, payload);
      App.showToast('Receta guardada exitosamente', 'success');
      this.closeRecipeModal();
      await this.load();
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  },

  async deleteCurrentRecipe() {
    if (!confirm('¿Desea eliminar la receta? El producto volverá a descontar únicamente su stock unitario.')) return;

    try {
      await API.deleteProductRecipe(this.recetaActual.productoId);
      App.showToast('Receta eliminada. Producto configurado como simple.', 'info');
      this.closeRecipeModal();
      await this.load();
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  },

  // ==========================================================================
  // Creación y Reabastecimiento de Insumos
  // ==========================================================================
  openNewInsumoModal() {
    document.getElementById('form-new-insumo').reset();
    document.getElementById('modal-new-insumo').classList.add('active');
  },

  closeNewInsumoModal() {
    document.getElementById('modal-new-insumo').classList.remove('active');
  },

  async handleCreateInsumo(e) {
    e.preventDefault();
    const codigo = document.getElementById('new-insumo-codigo').value.trim();
    const nombre = document.getElementById('new-insumo-nombre').value.trim();
    const unidad_medida = document.getElementById('new-insumo-unidad').value;
    const stock_actual = parseFloat(document.getElementById('new-insumo-stock').value);
    const stock_minimo = parseFloat(document.getElementById('new-insumo-minimo').value);
    const costo_unitario = parseFloat(document.getElementById('new-insumo-costo').value);

    try {
      await API.createInsumo({
        codigo,
        nombre,
        unidad_medida,
        stock_actual,
        stock_minimo,
        costo_unitario
      });
      App.showToast(`Materia prima '${nombre}' registrada exitosamente`, 'success');
      this.closeNewInsumoModal();
      await this.load();
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  },

  openReplenishInsumoModal(id, nombre, stockActual, unidad) {
    this.reabastecerInsumoSeleccionado = id;
    document.getElementById('replenish-insumo-name').textContent = nombre;
    document.getElementById('replenish-insumo-stock').textContent = stockActual;
    document.getElementById('replenish-insumo-unit').textContent = unidad;
    document.getElementById('replenish-insumo-cant-input').value = 100;
    document.getElementById('modal-replenish-insumo').classList.add('active');
  },

  closeReplenishInsumoModal() {
    document.getElementById('modal-replenish-insumo').classList.remove('active');
  },

  async handleReplenishInsumo(e) {
    e.preventDefault();
    if (!this.reabastecerInsumoSeleccionado) return;

    const cantidad = parseFloat(document.getElementById('replenish-insumo-cant-input').value);
    if (isNaN(cantidad) || cantidad <= 0) {
      App.showToast('Ingrese una cantidad válida mayor a cero', 'error');
      return;
    }

    try {
      const insumoActualizado = await API.replenishInsumo(this.reabastecerInsumoSeleccionado, cantidad);
      App.showToast(`Stock actualizado a ${insumoActualizado.stock_actual} ${insumoActualizado.unidad_medida}`, 'success');
      this.closeReplenishInsumoModal();
      await this.load();
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  },

  async handleDeleteInsumo(id, nombre) {
    if (!confirm(`¿Desea eliminar la materia prima '${nombre}'?`)) return;

    try {
      const res = await API.deleteInsumo(id);
      App.showToast(res.mensaje, res.tipo_eliminacion === 'fisica' ? 'success' : 'info');
      await this.load();
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  },

  // ==========================================================================
  // Creación y Modificación de Productos
  // ==========================================================================
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
