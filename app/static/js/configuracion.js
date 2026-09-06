/**
 * CoffeePOS - Módulo de Configuración & Mantenimiento Crítico
 * Controla ajustes del local, cantidad de mesas dinámicas, reinicio de stock y purga de fábrica.
 */

window.Configuracion = {
  async init() {
    this.bindEvents();
    await this.load();
  },

  bindEvents() {
    // Formulario de parámetros operativos
    const formConfig = document.getElementById('form-config-global');
    if (formConfig) {
      formConfig.addEventListener('submit', (e) => this.handleSaveConfig(e));
    }

    // Botón de Reinicio de Stock
    const btnResetStock = document.getElementById('btn-reset-stock-action');
    if (btnResetStock) {
      btnResetStock.addEventListener('click', () => this.handleResetStock());
    }

    // Botón de Limpieza Total
    const btnWipeDb = document.getElementById('btn-wipe-db-action');
    if (btnWipeDb) {
      btnWipeDb.addEventListener('click', () => this.handleWipeDatabase());
    }

    // Botón Cargar Catálogo Demo
    const btnLoadDemo = document.getElementById('btn-load-demo-seeds');
    if (btnLoadDemo) {
      btnLoadDemo.addEventListener('click', () => this.handleLoadDemoSeeds());
    }
  },

  async load() {
    try {
      const cfg = await API.getConfig();
      document.getElementById('cfg-mesas-input').value = cfg.mesas_activas;
      document.getElementById('cfg-nombre-input').value = cfg.nombre_local;
      document.getElementById('cfg-ticket-format').value = cfg.formato_ticket;
    } catch (err) {
      App.showToast('Error cargando parámetros de configuración', 'error');
    }
  },

  async handleSaveConfig(e) {
    e.preventDefault();
    const mesas_activas = parseInt(document.getElementById('cfg-mesas-input').value, 10);
    const nombre_local = document.getElementById('cfg-nombre-input').value.trim();
    const formato_ticket = document.getElementById('cfg-ticket-format').value;

    try {
      const updated = await API.updateConfig({
        mesas_activas,
        nombre_local,
        formato_ticket
      });
      App.config = updated;
      document.getElementById('header-local-name').textContent = updated.nombre_local;
      App.showToast('Configuración actualizada exitosamente', 'success');

      if (window.TPV) window.TPV.renderTables();
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  },

  async handleResetStock() {
    const confirmacion = confirm(
      '¿Está seguro de reiniciar el stock actual al valor inicial para todos los productos? Esta acción actualizará las existencias en el catálogo.'
    );
    if (!confirmacion) return;

    try {
      const res = await API.resetStock();
      App.showToast(res.mensaje, 'success');
      if (window.TPV) window.TPV.loadProducts();
      if (window.Inventario) window.Inventario.load();
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  },

  async handleWipeDatabase() {
    const input = prompt(
      '⚠️ ADVERTENCIA CRÍTICA: Esta acción eliminará todos los pedidos, tickets y restaurará la base de datos a su estado original de fábrica.\n\nPara confirmar, escriba exactamente la palabra: borrar'
    );

    if (!input) return;

    if (input.trim().toLowerCase() !== 'borrar') {
      App.showToast("Palabra clave incorrecta. Acción cancelada.", 'error');
      return;
    }

    try {
      const res = await API.wipeDatabase('borrar');
      App.showToast(res.mensaje, 'success');
      await App.loadGlobalConfig();
      if (window.TPV) window.TPV.refresh();
      if (window.Inventario) window.Inventario.load();
      if (window.Caja) window.Caja.loadSummary();
      this.load();
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  },

  async handleLoadDemoSeeds() {
    const confirmacion = confirm(
      '¿Desea cargar el catálogo oficial de 24 productos de cafetería en el inventario?'
    );
    if (!confirmacion) return;

    try {
      const res = await API.loadDemoSeeds();
      App.showToast(res.mensaje, 'success');
      if (window.TPV) window.TPV.refresh();
      if (window.Inventario) window.Inventario.load();
    } catch (err) {
      App.showToast(err.message, 'error');
    }
  }
};
