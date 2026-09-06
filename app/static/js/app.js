/**
 * CoffeePOS - Aplicación Principal (SPA Orchestrator)
 * Controla navegación de pestañas, notificaciones globales y reloj del sistema.
 */

const App = {
  config: {
    mesas_activas: 8,
    nombre_local: 'CoffeePOS Stand',
    moneda_simbolo: '$',
    formato_ticket: '80mm'
  },

  async init() {
    this.setupNavigation();
    this.setupClock();
    await this.loadGlobalConfig();

    // Inicializar submódulos
    if (window.TPV) window.TPV.init();
    if (window.Inventario) window.Inventario.init();
    if (window.Caja) window.Caja.init();
    if (window.Configuracion) window.Configuracion.init();
  },

  async loadGlobalConfig() {
    try {
      const cfg = await API.getConfig();
      this.config = cfg;
      document.getElementById('header-local-name').textContent = cfg.nombre_local;
    } catch (err) {
      console.warn('Usando configuración fallback por defecto:', err);
    }
  },

  setupNavigation() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const targetView = btn.dataset.view;
        this.switchTab(targetView);
      });
    });
  },

  switchTab(viewId) {
    // Actualizar botones
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.view === viewId);
    });

    // Actualizar vistas
    document.querySelectorAll('.view-section').forEach(sec => {
      sec.classList.toggle('active', sec.id === `view-${viewId}`);
    });

    // Refrescar datos según la vista activa
    if (viewId === 'tpv' && window.TPV) window.TPV.refresh();
    if (viewId === 'inventario' && window.Inventario) window.Inventario.load();
    if (viewId === 'caja' && window.Caja) window.Caja.loadSummary();
    if (viewId === 'config' && window.Configuracion) window.Configuracion.load();
  },

  setupClock() {
    const clockEl = document.getElementById('header-clock');
    if (!clockEl) return;
    const update = () => {
      const now = new Date();
      clockEl.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    };
    update();
    setInterval(update, 1000);
  },

  formatMoney(val) {
    const num = Number(val) || 0;
    return `${this.config.moneda_simbolo}${num.toLocaleString('es-CL', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  },

  showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '⚠️';

    toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }
};

document.addEventListener('DOMContentLoaded', () => {
  App.init();
});
