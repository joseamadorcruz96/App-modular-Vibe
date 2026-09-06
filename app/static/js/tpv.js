/**
 * CoffeePOS - Módulo TPV (Terminal Punto de Venta & Comandera)
 * Gestiona el flujo táctil de mesas, comanda persistente de salón,
 * catálogo con buscador, carrito temporal y checkout atómico.
 */

window.TPV = {
  mesaSeleccionada: 'Barra / Para Llevar',
  productos: [],
  carrito: [], // { producto, cantidad }
  mesasEstado: [], // Estados de mesas del salón desde API
  comandaActiva: null, // Comanda abierta en la mesa seleccionada (si aplica)
  medioPagoSeleccionado: 'Efectivo',

  async init() {
    this.bindEvents();
    await this.refresh();
  },

  bindEvents() {
    // Buscador rápido con debounce
    const searchInput = document.getElementById('tpv-search');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        this.renderProducts(e.target.value);
      });
    }

    // Botón principal de Cobro / Acción
    const btnCheckout = document.getElementById('btn-open-checkout');
    if (btnCheckout) {
      btnCheckout.addEventListener('click', () => this.handleMainAction());
    }

    // Botón de Enviar / Cargar a Mesa
    const btnCargarMesa = document.getElementById('btn-cargar-a-mesa');
    if (btnCargarMesa) {
      btnCargarMesa.addEventListener('click', () => this.handleEnviarAMesa());
    }

    // Botón de Servir Comanda de Mesa (descuenta stock en cocina/barra)
    const btnServirCmd = document.getElementById('btn-servir-mesa-cmd');
    if (btnServirCmd) {
      btnServirCmd.addEventListener('click', () => this.handleServirComanda());
    }

    // Botón de Cancelar Comanda de Mesa
    const btnCancelarCmd = document.getElementById('btn-cancelar-mesa-cmd');
    if (btnCancelarCmd) {
      btnCancelarCmd.addEventListener('click', () => this.handleCancelarComanda());
    }

    // Selector de Medio de Pago en Modal
    const paymentButtons = document.querySelectorAll('.payment-btn');
    paymentButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        paymentButtons.forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        this.medioPagoSeleccionado = btn.dataset.method;
      });
    });

    // Confirmar Cobro en Modal
    const btnConfirmCheckout = document.getElementById('btn-confirm-checkout');
    if (btnConfirmCheckout) {
      btnConfirmCheckout.addEventListener('click', () => this.processCheckout());
    }
  },

  async refresh() {
    await this.loadMesasEstado();
    await this.renderTables();
    await this.loadProducts();
    await this.syncSelectedTable();
  },

  async loadMesasEstado() {
    try {
      this.mesasEstado = await API.getMesasEstado();
    } catch (err) {
      console.error('Error obteniendo estado de mesas:', err);
      this.mesasEstado = [];
    }
  },

  async renderTables() {
    const container = document.getElementById('tpv-tables-carousel');
    if (!container) return;

    try {
      let html = `
        <button class="table-pill-btn ${this.mesaSeleccionada === 'Barra / Para Llevar' ? 'selected' : ''}" 
                onclick="TPV.selectMesa('Barra / Para Llevar')">
          ☕ Barra / Para Llevar
        </button>
      `;

      for (const m of this.mesasEstado) {
        const isSelected = this.mesaSeleccionada === m.mesa;
        const ocupada = m.ocupada;
        let badge = '🟢';
        let styleExtra = '';

        if (ocupada) {
          if (m.estado === 'Servida') {
            badge = '🍽️';
            styleExtra = 'border-color: #10b981; color: #10b981;';
          } else {
            badge = '⏳';
            styleExtra = 'border-color: #f59e0b; color: #f59e0b;';
          }
        }

        const label = ocupada 
          ? `${badge} ${m.mesa} (${App.formatMoney(m.subtotal)})`
          : `🟢 ${m.mesa}`;

        html += `
          <button class="table-pill-btn ${isSelected ? 'selected' : ''} ${ocupada ? 'occupied-table' : ''}" 
                  style="${styleExtra}"
                  onclick="TPV.selectMesa('${m.mesa}')">
            ${label}
          </button>
        `;
      }

      container.innerHTML = html;
      document.getElementById('cart-selected-table').textContent = this.mesaSeleccionada;
    } catch (err) {
      console.error('Error renderizando mesas:', err);
    }
  },

  async selectMesa(mesa) {
    this.mesaSeleccionada = mesa;
    this.renderTables();
    document.getElementById('cart-selected-table').textContent = mesa;
    await this.syncSelectedTable();
  },

  async syncSelectedTable() {
    const banner = document.getElementById('mesa-status-banner');
    const badgeInd = document.getElementById('mesa-badge-indicador');
    const estadoTexto = document.getElementById('mesa-estado-texto');
    const subtotalText = document.getElementById('mesa-comanda-subtotal');
    const mesaActionsGroup = document.getElementById('mesa-actions-group');
    const btnCargarMesa = document.getElementById('btn-cargar-a-mesa');
    const btnServirCmd = document.getElementById('btn-servir-mesa-cmd');

    if (this.mesaSeleccionada === 'Barra / Para Llevar') {
      if (banner) banner.style.display = 'none';
      if (mesaActionsGroup) mesaActionsGroup.style.display = 'none';
      this.comandaActiva = null;
      this.renderCart();
      return;
    }

    if (banner) banner.style.display = 'flex';
    if (mesaActionsGroup) mesaActionsGroup.style.display = 'flex';

    // Buscar comanda activa en el backend
    try {
      this.comandaActiva = await API.getComandaMesa(this.mesaSeleccionada);
    } catch (err) {
      this.comandaActiva = null;
    }

    if (this.comandaActiva) {
      const tienePendientes = (this.comandaActiva.detalles || []).some(d => d.descontado_stock === 0);

      if (this.comandaActiva.estado === 'Servida' && !tienePendientes) {
        if (badgeInd) badgeInd.style.background = '#10b981';
        if (estadoTexto) estadoTexto.textContent = `${this.mesaSeleccionada} (🍽️ Servida - ${this.comandaActiva.cliente})`;
        if (btnServirCmd) {
          btnServirCmd.style.display = 'inline-block';
          btnServirCmd.textContent = '✅ Todo Servido';
          btnServirCmd.disabled = true;
        }
      } else {
        if (badgeInd) badgeInd.style.background = '#f59e0b';
        if (estadoTexto) estadoTexto.textContent = `${this.mesaSeleccionada} (⏳ En Preparación - ${this.comandaActiva.cliente})`;
        if (btnServirCmd) {
          btnServirCmd.style.display = 'inline-block';
          btnServirCmd.textContent = '🍽️ Marcar Servido';
          btnServirCmd.disabled = false;
        }
      }

      if (subtotalText) subtotalText.textContent = `Consumo: ${App.formatMoney(this.comandaActiva.subtotal)}`;
      if (btnCargarMesa) btnCargarMesa.textContent = '➕ Agregar a Mesa';
    } else {
      if (badgeInd) badgeInd.style.background = '#10b981';
      if (estadoTexto) estadoTexto.textContent = `${this.mesaSeleccionada} (Libre)`;
      if (subtotalText) subtotalText.textContent = '$0';
      if (btnCargarMesa) btnCargarMesa.textContent = '📝 Abrir y Cargar Mesa';
      if (btnServirCmd) btnServirCmd.style.display = 'none';
    }

    this.renderCart();
  },

  async loadProducts() {
    try {
      this.productos = await API.getProducts('', true);
      this.renderProducts();
    } catch (err) {
      App.showToast('Error cargando catálogo de productos', 'error');
    }
  },

  renderProducts(filtro = '') {
    const grid = document.getElementById('tpv-products-grid');
    if (!grid) return;

    const term = filtro.toLowerCase().trim();
    const filtrados = this.productos.filter(p => 
      p.nombre.toLowerCase().includes(term) || p.codigo.toLowerCase().includes(term)
    );

    if (filtrados.length === 0) {
      grid.innerHTML = `
        <div style="grid-column: 1/-1; text-align: center; color: var(--text-dim); padding: 3rem;">
          <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🔍</div>
          <p>No se encontraron productos coincidentes.</p>
        </div>
      `;
      return;
    }

    grid.innerHTML = filtrados.map(prod => {
      const enStock = prod.stock_actual > 0;
      const isCritical = prod.stock_actual <= 5;
      const stockBadge = isCritical 
        ? `<span class="prod-stock-pill critical">🚨 Stock: ${prod.stock_actual}</span>`
        : `<span class="prod-stock-pill">Stock: ${prod.stock_actual}</span>`;

      return `
        <div class="product-card ${enStock ? '' : 'out-of-stock'}" 
             onclick="${enStock ? `TPV.addToCart(${prod.id})` : `App.showToast('Sin stock disponible para ${prod.nombre}', 'error')`}">
          <div>
            <div class="prod-code-badge">${prod.codigo}</div>
            <div class="prod-name">${prod.nombre}</div>
          </div>
          <div class="prod-footer">
            <div class="prod-price">${App.formatMoney(prod.precio_venta)}</div>
            <div>${stockBadge}</div>
          </div>
        </div>
      `;
    }).join('');
  },

  addToCart(productId) {
    const prod = this.productos.find(p => p.id === productId);
    if (!prod) return;

    const existing = this.carrito.find(item => item.producto.id === productId);
    const cantidadActual = existing ? existing.cantidad : 0;

    if (cantidadActual + 1 > prod.stock_actual) {
      App.showToast(`Stock máximo alcanzado para ${prod.nombre} (${prod.stock_actual} disp.)`, 'error');
      return;
    }

    if (existing) {
      existing.cantidad++;
    } else {
      this.carrito.push({ producto: prod, cantidad: 1 });
    }

    this.renderCart();
  },

  updateQuantity(productId, delta) {
    const item = this.carrito.find(i => i.producto.id === productId);
    if (!item) return;

    const nuevaCant = item.cantidad + delta;
    if (nuevaCant <= 0) {
      this.removeFromCart(productId);
      return;
    }

    if (nuevaCant > item.producto.stock_actual) {
      App.showToast(`Stock insuficiente. Solo quedan ${item.producto.stock_actual} unidades.`, 'error');
      return;
    }

    item.cantidad = nuevaCant;
    this.renderCart();
  },

  removeFromCart(productId) {
    this.carrito = this.carrito.filter(i => i.producto.id !== productId);
    this.renderCart();
  },

  clearCart() {
    this.carrito = [];
    this.renderCart();
  },

  renderCart() {
    const listEl = document.getElementById('tpv-cart-items');
    const totalEl = document.getElementById('tpv-cart-total');
    const btnCheckout = document.getElementById('btn-open-checkout');
    const btnCargarMesa = document.getElementById('btn-cargar-a-mesa');
    const btnCancelarCmd = document.getElementById('btn-cancelar-mesa-cmd');
    if (!listEl || !totalEl) return;

    let subtotalCarrito = this.carrito.reduce((acc, i) => acc + (i.producto.precio_venta * i.cantidad), 0);
    let subtotalComanda = this.comandaActiva ? this.comandaActiva.subtotal : 0;
    let granTotal = subtotalCarrito + subtotalComanda;

    // Renderizar ítems ya guardados en comanda + ítems nuevos por enviar
    let html = '';

    if (this.comandaActiva && this.comandaActiva.detalles.length > 0) {
      const estadoBadgeComanda = this.comandaActiva.estado === 'Servida'
        ? '<span style="color: #10b981; font-weight: 700; margin-left: 6px;">[🍽️ SERVIDA]</span>'
        : '<span style="color: #f59e0b; font-weight: 700; margin-left: 6px;">[⏳ EN PREPARACIÓN]</span>';

      html += `
        <div style="font-size: 0.75rem; font-weight: 700; color: var(--accent-gold); text-transform: uppercase; padding: 0.4rem 0; border-bottom: 1px dashed var(--border-subtle); display: flex; justify-content: space-between; align-items: center;">
          <span>Consumo en mesa (${this.comandaActiva.numero_comanda}):</span>
          <span>${estadoBadgeComanda}</span>
        </div>
      `;
      html += this.comandaActiva.detalles.map(item => {
        const servido = item.descontado_stock === 1;
        const itemStatusTag = servido
          ? '<span style="color: #10b981; font-size: 0.7rem; font-weight: 700; background: rgba(16, 185, 129, 0.1); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(16, 185, 129, 0.2);">✅ Servido</span>'
          : '<span style="color: #f59e0b; font-size: 0.7rem; font-weight: 700; background: rgba(245, 158, 11, 0.1); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(245, 158, 11, 0.2);">⏳ Preparando</span>';

        const btnServirIndividual = !servido
          ? `<button class="table-pill-btn" style="padding: 0.2rem 0.5rem; font-size: 0.72rem; border-color: #10b981; color: #10b981; margin-right: 4px;" onclick="TPV.handleServirItem(${item.id})" title="Marcar servido y descontar stock de inmediato">🍽️ Servir</button>`
          : '';

        return `
          <div class="cart-item-row" style="background: rgba(255,255,255,0.02); align-items: center;">
            <div class="cart-item-info" style="flex: 1;">
              <div class="cart-item-name" style="display: flex; align-items: center; gap: 4px; flex-wrap: wrap;">
                <span>${item.nombre}</span>
                ${itemStatusTag}
              </div>
              <div class="cart-item-unit-price">${item.cantidad}x ${App.formatMoney(item.precio_unitario)}</div>
            </div>
            <div class="cart-item-subtotal">${App.formatMoney(item.subtotal)}</div>
            <div style="display: flex; align-items: center;">
              ${btnServirIndividual}
              <button class="cart-item-remove" onclick="TPV.removeComandaItem(${item.id})" title="Quitar de la mesa">🗑️</button>
            </div>
          </div>
        `;
      }).join('');
    }

    if (this.carrito.length > 0) {
      if (this.comandaActiva) {
        html += `
          <div style="font-size: 0.75rem; font-weight: 700; color: #34d399; text-transform: uppercase; padding: 0.4rem 0; margin-top: 0.5rem; border-bottom: 1px dashed var(--border-subtle);">
            Nuevos ítems por enviar a mesa:
          </div>
        `;
      }
      html += this.carrito.map(item => {
        const subtotal = item.producto.precio_venta * item.cantidad;
        return `
          <div class="cart-item-row">
            <div class="cart-item-info">
              <div class="cart-item-name">${item.producto.nombre}</div>
              <div class="cart-item-unit-price">${App.formatMoney(item.producto.precio_venta)} c/u</div>
            </div>
            <div class="cart-stepper">
              <button class="stepper-btn" onclick="TPV.updateQuantity(${item.producto.id}, -1)">−</button>
              <span class="stepper-value">${item.cantidad}</span>
              <button class="stepper-btn" onclick="TPV.updateQuantity(${item.producto.id}, 1)">+</button>
            </div>
            <div class="cart-item-subtotal">${App.formatMoney(subtotal)}</div>
            <button class="cart-item-remove" onclick="TPV.removeFromCart(${item.producto.id})" title="Eliminar">🗑️</button>
          </div>
        `;
      }).join('');
    }

    if (!this.comandaActiva && this.carrito.length === 0) {
      listEl.innerHTML = `
        <div class="cart-empty-state">
          <div class="icon">🛒</div>
          <p style="font-weight: 600;">Comanda vacía</p>
          <span style="font-size: 0.8rem;">Seleccione productos para comenzar el pedido.</span>
        </div>
      `;
      totalEl.textContent = App.formatMoney(0);
      if (btnCheckout) {
        btnCheckout.disabled = true;
        btnCheckout.innerHTML = '<span>⚡</span><span>COBRAR TICKET</span>';
      }
      if (btnCargarMesa) btnCargarMesa.disabled = true;
      if (btnCancelarCmd) btnCancelarCmd.disabled = true;
      return;
    }

    listEl.innerHTML = html;
    totalEl.textContent = App.formatMoney(granTotal);

    // Ajuste dinámico de botones
    if (btnCheckout) {
      if (this.comandaActiva) {
        btnCheckout.disabled = false;
        btnCheckout.innerHTML = `<span>💳</span><span>COBRAR MESA (${App.formatMoney(granTotal)})</span>`;
      } else {
        btnCheckout.disabled = (this.carrito.length === 0);
        btnCheckout.innerHTML = '<span>⚡</span><span>COBRAR DIRECTO</span>';
      }
    }

    if (btnCargarMesa) {
      btnCargarMesa.disabled = (this.carrito.length === 0);
    }

    if (btnCancelarCmd) {
      btnCancelarCmd.disabled = (!this.comandaActiva);
    }
  },

  async handleMainAction() {
    // Si la mesa tiene comanda activa y además hay ítems en carrito, enviar primero los ítems
    if (this.comandaActiva && this.carrito.length > 0) {
      await this.handleEnviarAMesa(false);
    }
    this.openCheckoutModal();
  },

  async handleEnviarAMesa(mostrarNotificacion = true) {
    if (this.carrito.length === 0) {
      App.showToast('Agregue productos al carrito antes de enviar a la mesa.', 'warning');
      return;
    }

    const clienteInput = document.getElementById('checkout-cliente-input');
    const cliente = clienteInput ? clienteInput.value.trim() : 'Consumidor Final';

    try {
      let comandaId;
      if (!this.comandaActiva) {
        // 1. Abrir comanda en la mesa
        const nuevaCmd = await API.openComanda(this.mesaSeleccionada, cliente || 'Consumidor Final');
        comandaId = nuevaCmd.id;
      } else {
        comandaId = this.comandaActiva.id;
      }

      // 2. Agregar ítems del carrito
      const itemsPayload = this.carrito.map(i => ({
        producto_id: i.producto.id,
        cantidad: i.cantidad
      }));
      await API.addComandaItems(comandaId, itemsPayload);

      this.clearCart();
      await this.refresh();

      if (mostrarNotificacion) {
        App.showToast(`Productos cargados a ${this.mesaSeleccionada} (En preparación)`, 'success');
      }
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  },

  async handleServirComanda() {
    if (!this.comandaActiva) return;
    try {
      await API.serveComanda(this.comandaActiva.id);
      App.showToast('🍽️ ¡Comanda servida! Stock de barra y cocina descontado.', 'success');
      await this.refresh();
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  },

  async handleServirItem(detalleId) {
    if (!this.comandaActiva) return;
    try {
      await API.serveComandaItem(this.comandaActiva.id, detalleId);
      App.showToast('🍽️ Ítem marcado como servido y stock descontado.', 'success');
      await this.refresh();
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  },

  async removeComandaItem(detalleId) {
    if (!this.comandaActiva) return;
    const item = (this.comandaActiva.detalles || []).find(d => d.id === detalleId);
    if (!item) return;

    let restaurarStock = false;
    if (item.descontado_stock === 1) {
      const resp = confirm(
        `El producto "${item.nombre}" ya fue SERVIDO (su stock fue descontado).\n\n` +
        `¿Desea RESTAURAR su stock al inventario?\n\n` +
        `• [Aceptar]: RESTAURAR existencias al inventario.\n` +
        `• [Cancelar]: Anular como MERMA / DESPERDICIO (sin reponer stock).`
      );
      restaurarStock = resp;
    } else {
      if (!confirm(`¿Desea quitar "${item.nombre}" de la mesa?`)) return;
    }

    try {
      await API.removeComandaItem(this.comandaActiva.id, detalleId, restaurarStock);
      App.showToast(
        restaurarStock ? 'Producto retirado y stock restaurado' : 'Producto retirado (merma)',
        'info'
      );
      await this.refresh();
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  },

  async handleCancelarComanda() {
    if (!this.comandaActiva) return;
    const tieneServidos = (this.comandaActiva.detalles || []).some(d => d.descontado_stock === 1);
    if (tieneServidos) {
      const modal = document.getElementById('modal-cancelar-comanda');
      if (modal) {
        modal.classList.add('active');
        return;
      }
    }

    if (!confirm(`¿Desea cancelar la comanda abierta de ${this.mesaSeleccionada}? La mesa quedará libre.`)) return;
    await this.ejecutarCancelarComanda(false);
  },

  closeCancelarModal() {
    const modal = document.getElementById('modal-cancelar-comanda');
    if (modal) modal.classList.remove('active');
  },

  async ejecutarCancelarComanda(restaurarStock = false) {
    if (!this.comandaActiva) return;
    try {
      await API.cancelComanda(this.comandaActiva.id, restaurarStock);
      App.showToast(
        restaurarStock
          ? `Comanda cancelada. Stock reincorporado al inventario.`
          : `Comanda cancelada y registrada como merma/desperdicio.`,
        'info'
      );
      this.closeCancelarModal();
      this.clearCart();
      await this.refresh();
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  },

  openCheckoutModal() {
    const totalCarrito = this.carrito.reduce((acc, i) => acc + (i.producto.precio_venta * i.cantidad), 0);
    const totalComanda = this.comandaActiva ? this.comandaActiva.subtotal : 0;
    const total = totalCarrito + totalComanda;

    if (total <= 0) return;

    const modal = document.getElementById('modal-checkout');
    document.getElementById('checkout-modal-mesa').textContent = this.mesaSeleccionada;
    document.getElementById('checkout-modal-total').textContent = App.formatMoney(total);

    modal.classList.add('active');
  },

  closeCheckoutModal() {
    document.getElementById('modal-checkout').classList.remove('active');
  },

  async processCheckout() {
    const btn = document.getElementById('btn-confirm-checkout');
    const clienteInput = document.getElementById('checkout-cliente-input');
    const cliente = clienteInput ? clienteInput.value.trim() : 'Consumidor Final';

    btn.disabled = true;
    btn.textContent = 'Procesando Transacción...';

    try {
      let ticket;

      if (this.comandaActiva) {
        // Liquidar comanda abierta
        // Si había algo extra en el carrito, se añade antes
        if (this.carrito.length > 0) {
          const itemsPayload = this.carrito.map(i => ({
            producto_id: i.producto.id,
            cantidad: i.cantidad
          }));
          await API.addComandaItems(this.comandaActiva.id, itemsPayload);
          this.clearCart();
        }

        ticket = await API.checkoutComanda(this.comandaActiva.id, {
          medio_pago: this.medioPagoSeleccionado,
          descuento: 0.0
        });
      } else {
        // Venta directa estándar
        const payload = {
          mesa: this.mesaSeleccionada,
          cliente: cliente || 'Consumidor Final',
          medio_pago: this.medioPagoSeleccionado,
          items: this.carrito.map(i => ({
            producto_id: i.producto.id,
            cantidad: i.cantidad
          }))
        };
        ticket = await API.checkout(payload);
      }

      App.showToast(`Ticket ${ticket.numero_ticket} emitido exitosamente`, 'success');
      this.closeCheckoutModal();
      this.clearCart();
      await this.refresh();

      // Mostrar comprobante térmico
      this.showTicketPrintModal(ticket);
    } catch (err) {
      App.showToast(err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '⚡ Confirmar y Cobrar Ticket';
    }
  },

  showTicketPrintModal(ticket) {
    const modal = document.getElementById('modal-ticket-print');
    const content = document.getElementById('ticket-print-content');

    const filasHtml = ticket.detalles.map(d => `
      <tr>
        <td>${d.cantidad}x ${d.nombre}</td>
        <td style="text-align: right;">${App.formatMoney(d.subtotal)}</td>
      </tr>
    `).join('');

    content.innerHTML = `
      <div class="ticket-container">
        <div class="ticket-header">
          <h2 style="font-size: 1.1rem; font-weight: 800; margin-bottom: 2px;">${App.config.nombre_local}</h2>
          <div style="font-size: 0.8rem;">BOLETA / TICKET DE VENTA</div>
          <div style="font-weight: 700; margin-top: 4px;">${ticket.numero_ticket}</div>
          <div style="font-size: 0.75rem; color: #555;">Fecha: ${ticket.fecha_hora}</div>
          <div style="font-size: 0.8rem; font-weight: 600;">${ticket.mesa} | ${ticket.cliente}</div>
        </div>
        <table class="ticket-table">
          <thead>
            <tr style="border-bottom: 1px dashed #999;">
              <th>ÍTEM</th>
              <th style="text-align: right;">TOTAL</th>
            </tr>
          </thead>
          <tbody>
            ${filasHtml}
          </tbody>
        </table>
        <div class="ticket-footer">
          <div style="display: flex; justify-content: space-between; font-weight: 800; font-size: 1rem; margin-bottom: 4px;">
            <span>TOTAL:</span>
            <span>${App.formatMoney(ticket.total)}</span>
          </div>
          <div style="font-size: 0.8rem; margin-bottom: 8px;">Medio de Pago: ${ticket.medio_pago}</div>
          <div style="font-size: 0.75rem;">¡Gracias por su preferencia!</div>
        </div>
      </div>
    `;

    modal.classList.add('active');
  },

  closeTicketPrintModal() {
    document.getElementById('modal-ticket-print').classList.remove('active');
  },

  printTicket() {
    window.print();
  }
};
