/**
 * CoffeePOS - Módulo de Cierre de Caja & Reportes Diarios
 * Controla el balance financiero, arqueo por medio de pago, ranking de ventas y respaldos .db.
 */

window.Caja = {
  resumenActual: null,

  async init() {
    this.bindEvents();
    await this.loadSummary();
  },

  bindEvents() {
    const btnCerrar = document.getElementById('btn-ejecutar-cierre');
    if (btnCerrar) {
      btnCerrar.addEventListener('click', () => this.confirmarCierreCaja());
    }

    const btnImprimir = document.getElementById('btn-imprimir-reporte-dia');
    if (btnImprimir) {
      btnImprimir.addEventListener('click', () => this.imprimirReporte());
    }
  },

  async loadSummary() {
    try {
      const resumen = await API.getDailySummary();
      this.resumenActual = resumen;
      this.renderSummary(resumen);
    } catch (err) {
      App.showToast('Error al cargar balance diario de caja', 'error');
    }
  },

  renderSummary(r) {
    document.getElementById('stat-total-dia').textContent = App.formatMoney(r.total_recaudado);
    document.getElementById('stat-tickets-dia').textContent = r.cantidad_tickets;
    document.getElementById('stat-efectivo-dia').textContent = App.formatMoney(r.desglose_medios_pago['Efectivo'] || 0);
    document.getElementById('stat-debito-dia').textContent = App.formatMoney(r.desglose_medios_pago['Débito'] || 0);
    document.getElementById('stat-credito-dia').textContent = App.formatMoney(r.desglose_medios_pago['Crédito'] || 0);
    document.getElementById('stat-transfer-dia').textContent = App.formatMoney(r.desglose_medios_pago['Transferencia'] || 0);

    // Ranking de productos top
    const topContainer = document.getElementById('caja-top-productos-list');
    if (!topContainer) return;

    if (!r.productos_top || r.productos_top.length === 0) {
      topContainer.innerHTML = `
        <div style="text-align: center; color: var(--text-dim); padding: 1.5rem;">
          No hay ventas registradas en la fecha actual.
        </div>
      `;
      return;
    }

    const maxVentas = Math.max(...r.productos_top.map(p => p.unidades_vendidas), 1);

    topContainer.innerHTML = r.productos_top.map((item, idx) => {
      const porcentaje = Math.round((item.unidades_vendidas / maxVentas) * 100);
      return `
        <div style="background: var(--bg-card); padding: 0.85rem 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
          <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.4rem;">
            <div style="font-weight: 700; font-size: 0.95rem;">
              <span style="color: var(--primary); margin-right: 0.5rem;">#${idx + 1}</span> ${item.nombre}
            </div>
            <div style="font-family: var(--font-mono); font-weight: 800; color: var(--accent-gold);">
              ${item.unidades_vendidas} un. (${App.formatMoney(item.total_recaudado)})
            </div>
          </div>
          <div style="background: var(--bg-main); height: 6px; border-radius: var(--radius-full); overflow: hidden;">
            <div style="background: linear-gradient(90deg, #d97706, #f59e0b); height: 100%; width: ${porcentaje}%;"></div>
          </div>
        </div>
      `;
    }).join('');
  },

  async confirmarCierreCaja() {
    if (!confirm('¿Desea ejecutar el Cierre de Caja del día? Se generará una copia de respaldo automática en /backups.')) {
      return;
    }

    try {
      const res = await API.closeRegister();
      App.showToast(`Cierre exitoso. Respaldo: ${res.backup_generado}`, 'success');
      await this.loadSummary();
      this.mostrarReporteImprimible(res.resumen, res.backup_generado);
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  },

  imprimirReporte() {
    if (!this.resumenActual) {
      App.showToast('No hay datos disponibles para imprimir', 'error');
      return;
    }
    this.mostrarReporteImprimible(this.resumenActual);
  },

  mostrarReporteImprimible(resumen, backupNombre = '') {
    const modal = document.getElementById('modal-reporte-cierre-print');
    const content = document.getElementById('reporte-cierre-content');

    const topHtml = (resumen.productos_top || []).map(p => `
      <tr>
        <td>${p.nombre}</td>
        <td style="text-align: center;">${p.unidades_vendidas}</td>
        <td style="text-align: right;">${App.formatMoney(p.total_recaudado)}</td>
      </tr>
    `).join('');

    content.innerHTML = `
      <div class="ticket-container" style="text-align: left;">
        <div class="ticket-header" style="text-align: center;">
          <h2 style="font-size: 1.1rem; font-weight: 800;">${App.config.nombre_local}</h2>
          <div style="font-weight: 700; font-size: 0.9rem;">REPORTE DE CIERRE DE CAJA</div>
          <div style="font-size: 0.8rem; color: #555;">Fecha: ${resumen.fecha}</div>
          ${backupNombre ? `<div style="font-size: 0.65rem; color: #777;">Backup: ${backupNombre}</div>` : ''}
        </div>

        <div style="margin: 8px 0; border-bottom: 1px dashed #999; padding-bottom: 6px;">
          <div style="display: flex; justify-content: space-between; font-weight: 800; font-size: 1.05rem;">
            <span>TOTAL RECAUDADO:</span>
            <span>${App.formatMoney(resumen.total_recaudado)}</span>
          </div>
          <div style="font-size: 0.8rem; margin-top: 4px;">Tickets Emitidos: <strong>${resumen.cantidad_tickets}</strong></div>
        </div>

        <div style="margin: 8px 0; border-bottom: 1px dashed #999; padding-bottom: 6px;">
          <div style="font-weight: 700; font-size: 0.85rem; margin-bottom: 4px;">DESGLOSE POR MEDIO DE PAGO:</div>
          <table style="width: 100%; font-size: 0.8rem;">
            <tr><td>• Efectivo:</td><td style="text-align: right;">${App.formatMoney(resumen.desglose_medios_pago['Efectivo'] || 0)}</td></tr>
            <tr><td>• Débito:</td><td style="text-align: right;">${App.formatMoney(resumen.desglose_medios_pago['Débito'] || 0)}</td></tr>
            <tr><td>• Crédito:</td><td style="text-align: right;">${App.formatMoney(resumen.desglose_medios_pago['Crédito'] || 0)}</td></tr>
            <tr><td>• Transferencia:</td><td style="text-align: right;">${App.formatMoney(resumen.desglose_medios_pago['Transferencia'] || 0)}</td></tr>
          </table>
        </div>

        <div style="margin: 8px 0;">
          <div style="font-weight: 700; font-size: 0.85rem; margin-bottom: 4px;">PRODUCTOS MÁS VENDIDOS:</div>
          <table style="width: 100%; font-size: 0.75rem;">
            <thead>
              <tr style="border-bottom: 1px solid #ccc;">
                <th>Producto</th>
                <th style="text-align: center;">Cant.</th>
                <th style="text-align: right;">Total</th>
              </tr>
            </thead>
            <tbody>
              ${topHtml || '<tr><td colspan="3">Sin ventas registradas</td></tr>'}
            </tbody>
          </table>
        </div>

        <div class="ticket-footer" style="margin-top: 12px; font-size: 0.75rem; text-align: center;">
          --- Fin del Reporte ---
        </div>
      </div>
    `;

    modal.classList.add('active');
  },

  closeReporteModal() {
    document.getElementById('modal-reporte-cierre-print').classList.remove('active');
  }
};
