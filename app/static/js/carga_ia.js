/**
 * CoffeePOS - Módulo de Carga Automática con IA
 * Diseñado especialmente para usuarios sin conocimientos informáticos.
 * Permite copiar el prompt maestro, procesar tablas Markdown o archivos .md/.txt,
 * previsualizar los productos detectados y agregarlos atómicamente al inventario.
 */

const CargaIA = {
  catalogoExistente: [],
  productosDetectados: [],

  PROMPT_MAESTRO: `Actúa como un asistente administrativo experto para la cafetería "Coffee SoKa".
Te proporcionaré una lista de productos que llegaron hoy (puede ser texto desordenado, una transcripción de voz o datos de una factura de compras).

Por favor, analiza los datos y devuélveme ÚNICAMENTE una tabla en formato Markdown con estas 5 columnas exactas:
| Codigo | Nombre | Stock | Costo | Precio |

Reglas que debes seguir rigurosamente:
1. Si un producto no tiene código, crea uno corto con letras y números (ej: MED01, EMP02, CAF03).
2. "Stock" debe ser la cantidad de unidades que entraron hoy (número entero).
3. "Costo" es el costo unitario de compra (número puro, sin signos $ ni puntos de miles).
4. "Precio" es el precio sugerido de venta al cliente. Si no te lo di, estima un precio con al menos 50% de ganancia.
5. Devuelve EXCLUSIVAMENTE la tabla Markdown, sin saludos, sin explicaciones ni bloques de texto adicionales, para que el sistema la lea directamente.

Mis productos de hoy son:
[PEGA AQUÍ TU LISTA, FOTO DE FACTURA O NOTA DE VOZ]`,

  init() {
    this.bindEvents();
  },

  async load() {
    // Cargar catálogo actual para comparar en la previsualización
    try {
      this.catalogoExistente = await API.getProducts('', false);
    } catch (err) {
      console.warn('No se pudo precargar el catálogo para previsualización:', err);
      this.catalogoExistente = [];
    }
  },

  bindEvents() {
    // Botón para copiar el prompt maestro
    const btnCopiarPrompt = document.getElementById('btn-copiar-prompt-ia');
    if (btnCopiarPrompt) {
      btnCopiarPrompt.addEventListener('click', () => this.copiarPrompt());
    }

    // Botón para procesar texto
    const btnProcesar = document.getElementById('btn-procesar-texto-ia');
    if (btnProcesar) {
      btnProcesar.addEventListener('click', () => this.procesarEntradaManual());
    }

    // Botón para limpiar área
    const btnLimpiar = document.getElementById('btn-limpiar-carga-ia');
    if (btnLimpiar) {
      btnLimpiar.addEventListener('click', () => this.limpiarTodo());
    }

    // Botón de confirmación e importación
    const btnConfirmar = document.getElementById('btn-confirmar-carga-ia');
    if (btnConfirmar) {
      btnConfirmar.addEventListener('click', () => this.confirmarImportacion());
    }

    // Zona Drag and Drop
    const dropzone = document.getElementById('dropzone-ia');
    const fileInput = document.getElementById('file-input-ia');

    if (dropzone && fileInput) {
      dropzone.addEventListener('click', () => fileInput.click());

      dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('drag-active');
      });

      dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('drag-active');
      });

      dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('drag-active');
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
          this.manejarArchivo(e.dataTransfer.files[0]);
        }
      });

      fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
          this.manejarArchivo(e.target.files[0]);
        }
      });
    }
  },

  async copiarPrompt() {
    try {
      await navigator.clipboard.writeText(this.PROMPT_MAESTRO);
      App.showToast('¡Instrucciones copiadas! Pégalas en ChatGPT, Claude o Gemini con tus productos.', 'success');
      
      const btn = document.getElementById('btn-copiar-prompt-ia');
      if (btn) {
        const textoOriginal = btn.innerHTML;
        btn.innerHTML = '<span>✅</span><span>¡Instrucción Copiada!</span>';
        btn.style.borderColor = 'var(--success)';
        setTimeout(() => {
          btn.innerHTML = textoOriginal;
          btn.style.borderColor = '';
        }, 3000);
      }
    } catch (err) {
      // Fallback para navegadores antiguos
      const textarea = document.createElement('textarea');
      textarea.value = this.PROMPT_MAESTRO;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      App.showToast('¡Instrucciones copiadas al portapapeles!', 'success');
    }
  },

  manejarArchivo(file) {
    if (!file) return;
    const extension = file.name.split('.').pop().toLowerCase();
    if (!['md', 'txt', 'csv'].includes(extension)) {
      App.showToast('Por favor sube un archivo de texto o Markdown (.md, .txt)', 'error');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const contenido = e.target.result;
      const textarea = document.getElementById('textarea-ia');
      if (textarea) textarea.value = contenido;
      App.showToast(`Archivo "${file.name}" cargado con éxito.`, 'info');
      this.procesarTexto(contenido);
    };
    reader.readAsText(file);
  },

  procesarEntradaManual() {
    const textarea = document.getElementById('textarea-ia');
    const texto = textarea ? textarea.value.trim() : '';
    if (!texto) {
      App.showToast('Por favor pega el texto generado por la IA o sube un archivo.', 'warning');
      return;
    }
    this.procesarTexto(texto);
  },

  limpiarTodo() {
    const textarea = document.getElementById('textarea-ia');
    if (textarea) textarea.value = '';
    const fileInput = document.getElementById('file-input-ia');
    if (fileInput) fileInput.value = '';
    this.productosDetectados = [];
    this.renderPrevisualizacion();
    App.showToast('Área de trabajo reiniciada.', 'info');
  },

  // Parser robusto tolerante a Markdown, pipes y CSV
  procesarTexto(textoBruto) {
    const lineas = textoBruto.split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0);
    if (lineas.length === 0) {
      App.showToast('El texto ingresado está vacío.', 'warning');
      return;
    }

    const productos = [];
    let enTabla = false;
    let encabezadosIndex = { codigo: -1, nombre: -1, stock: -1, costo: -1, precio: -1 };

    for (let i = 0; i < lineas.length; i++) {
      let linea = lineas[i];

      // Detectar línea de tabla Markdown
      if (linea.includes('|')) {
        // Desarmar celdas
        const partes = linea.split('|').map(p => p.trim());
        // Eliminar elementos vacíos en los extremos si la línea empezaba o terminaba con |
        if (partes.length > 0 && partes[0] === '') partes.shift();
        if (partes.length > 0 && partes[partes.length - 1] === '') partes.pop();

        if (partes.length < 3) continue;

        // Verificar si es separador markdown ej: |---|---|
        if (partes.every(p => /^:?-+:?$/.test(p))) {
          enTabla = true;
          continue;
        }

        // Buscar encabezados
        const partesLower = partes.map(p => p.toLowerCase());
        const esEncabezado = partesLower.some(p => 
          p.includes('nombre') || p.includes('producto') || p.includes('codigo') || p.includes('código') || p.includes('stock')
        );

        if (esEncabezado) {
          partesLower.forEach((p, idx) => {
            if (p.includes('cod')) encabezadosIndex.codigo = idx;
            else if (p.includes('nom') || p.includes('prod') || p.includes('art')) encabezadosIndex.nombre = idx;
            else if (p.includes('stock') || p.includes('cant')) encabezadosIndex.stock = idx;
            else if (p.includes('cost')) encabezadosIndex.costo = idx;
            else if (p.includes('prec') || p.includes('venta') || p.includes('pvp')) encabezadosIndex.precio = idx;
          });
          enTabla = true;
          continue;
        }

        // Fila de datos
        const prod = this.extraerProductoDeFila(partes, encabezadosIndex);
        if (prod && prod.nombre) {
          productos.push(prod);
        }
      } else if (linea.includes(',') || linea.includes(';')) {
        // Posible CSV
        const separador = linea.includes(';') ? ';' : ',';
        const partes = linea.split(separador).map(p => p.trim());
        if (partes.length >= 3) {
          const prod = this.extraerProductoDeFila(partes, encabezadosIndex);
          if (prod && prod.nombre) productos.push(prod);
        }
      }
    }

    if (productos.length === 0) {
      App.showToast('No se pudieron detectar productos en el texto. Revisa que tenga formato de tabla.', 'error');
      return;
    }

    this.productosDetectados = productos;
    this.renderPrevisualizacion();
    App.showToast(`¡Se detectaron ${productos.length} productos listos para revisar!`, 'success');

    // Desplazar suavemente a la previsualización
    const previewSection = document.getElementById('seccion-previsualizacion-ia');
    if (previewSection) {
      previewSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  },

  extraerProductoDeFila(partes, indices) {
    let codigo = '';
    let nombre = '';
    let stock = 0;
    let costo = 0;
    let precio = 0;

    if (indices.nombre !== -1) {
      nombre = partes[indices.nombre] || '';
      codigo = indices.codigo !== -1 ? (partes[indices.codigo] || '') : '';
      stock = indices.stock !== -1 ? this.limpiarNumero(partes[indices.stock]) : 0;
      costo = indices.costo !== -1 ? this.limpiarNumero(partes[indices.costo]) : 0;
      precio = indices.precio !== -1 ? this.limpiarNumero(partes[indices.precio]) : 0;
    } else {
      // Detección posicional por defecto: [Codigo, Nombre, Stock, Costo, Precio]
      if (partes.length >= 5) {
        codigo = partes[0];
        nombre = partes[1];
        stock = this.limpiarNumero(partes[2]);
        costo = this.limpiarNumero(partes[3]);
        precio = this.limpiarNumero(partes[4]);
      } else if (partes.length === 4) {
        // [Nombre, Stock, Costo, Precio]
        nombre = partes[0];
        stock = this.limpiarNumero(partes[1]);
        costo = this.limpiarNumero(partes[2]);
        precio = this.limpiarNumero(partes[3]);
      } else if (partes.length === 3) {
        // [Nombre, Stock, Precio]
        nombre = partes[0];
        stock = this.limpiarNumero(partes[1]);
        precio = this.limpiarNumero(partes[2]);
      }
    }

    nombre = nombre.replace(/^[*_~`]+|[*_~`]+$/g, '').trim();
    codigo = codigo.replace(/^[*_~`]+|[*_~`]+$/g, '').trim().toUpperCase();

    if (!nombre) return null;

    return {
      codigo: codigo || null,
      nombre: nombre,
      stock: Math.max(0, parseInt(stock, 10) || 0),
      costo_unitario: Math.max(0, parseFloat(costo) || 0),
      precio_venta: Math.max(0, parseFloat(precio) || 0)
    };
  },

  limpiarNumero(val) {
    if (val === undefined || val === null) return 0;
    let s = String(val).trim();
    // Quitar símbolos de moneda y caracteres de texto
    s = s.replace(/[$€USDCLP\s]/gi, '');
    
    // Si contiene punto y coma, determinar separador decimal
    if (s.includes('.') && s.includes(',')) {
      // Asumir formato español ej 1.500,50 -> 1500.50
      s = s.replace(/\./g, '').replace(',', '.');
    } else if (s.includes(',')) {
      // 1500,50 -> 1500.50
      s = s.replace(',', '.');
    } else if (s.includes('.')) {
      // Si tiene solo puntos, puede ser 1.500 (miles) o 15.5 (decimal)
      const partes = s.split('.');
      if (partes.length === 2 && partes[1].length === 3 && parseInt(partes[0], 10) < 1000) {
        // Probable separador de miles ej 1.500
        s = s.replace('.', '');
      }
    }

    const num = parseFloat(s);
    return isNaN(num) ? 0 : num;
  },

  renderPrevisualizacion() {
    const contenedor = document.getElementById('seccion-previsualizacion-ia');
    const tbody = document.getElementById('tabla-previsualizacion-ia-body');
    const statsContainer = document.getElementById('stats-previsualizacion-ia');

    if (!contenedor || !tbody) return;

    if (this.productosDetectados.length === 0) {
      contenedor.style.display = 'none';
      tbody.innerHTML = '';
      return;
    }

    contenedor.style.display = 'block';

    let totalProductos = this.productosDetectados.length;
    let nuevos = 0;
    let existentes = 0;
    let inversionTotal = 0;
    let valorVentaTotal = 0;

    tbody.innerHTML = this.productosDetectados.map((prod, idx) => {
      // Verificar si ya existe en el catálogo por código o por nombre
      const match = this.catalogoExistente.find(p => 
        (prod.codigo && p.codigo.toUpperCase() === prod.codigo.toUpperCase()) ||
        (p.nombre.toLowerCase().trim() === prod.nombre.toLowerCase().trim())
      );

      if (match) {
        existentes++;
      } else {
        nuevos++;
      }

      inversionTotal += (prod.stock * prod.costo_unitario);
      valorVentaTotal += (prod.stock * prod.precio_venta);

      const margen = prod.precio_venta > 0 
        ? Math.round(((prod.precio_venta - prod.costo_unitario) / prod.precio_venta) * 100) 
        : 0;

      const estadoBadge = match
        ? `<span class="badge-stock-warning" title="Se sumará el stock al producto existente (Stock actual: ${match.stock_actual})">🟡 Sumar a Existente</span>`
        : `<span class="badge-stock-normal" style="background: rgba(16,185,129,0.2); color: #10b981; border: 1px solid rgba(16,185,129,0.4);">🟢 Nuevo Producto</span>`;

      return `
        <tr>
          <td style="text-align: center;">${estadoBadge}</td>
          <td style="font-family: var(--font-mono); font-weight: 700; color: var(--accent-gold);">
            ${prod.codigo ? prod.codigo : '<span style="color: var(--text-dim); font-style: italic;">Auto (generado)</span>'}
          </td>
          <td style="font-weight: 600; color: var(--accent-cream);">${prod.nombre}</td>
          <td style="text-align: right; font-weight: 700;">+${prod.stock} un.</td>
          <td style="text-align: right;">${App.formatMoney(prod.costo_unitario)}</td>
          <td style="text-align: right; font-weight: 700; color: var(--accent-cream);">${App.formatMoney(prod.precio_venta)}</td>
          <td style="text-align: center;">
            <span style="font-size: 0.85rem; font-weight: 700; color: ${margen >= 40 ? 'var(--success)' : (margen > 0 ? 'var(--warning)' : 'var(--danger)')};">
              ${margen}%
            </span>
          </td>
          <td style="text-align: center;">
            <button class="btn-action-icon btn-del-item" onclick="CargaIA.eliminarDePrevisualizacion(${idx})" title="Quitar de esta carga">
              🗑️
            </button>
          </td>
        </tr>
      `;
    }).join('');

    // Actualizar tarjetas de estadísticas resumen
    if (statsContainer) {
      statsContainer.innerHTML = `
        <div class="stat-card">
          <div class="stat-label">Total Detectados</div>
          <div class="stat-value" style="color: var(--accent-gold);">${totalProductos}</div>
          <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 4px;">
            ${nuevos} nuevos · ${existentes} existentes
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Inversión en Costo</div>
          <div class="stat-value">${App.formatMoney(inversionTotal)}</div>
          <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 4px;">Costo de mercadería</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Valor Venta Estimado</div>
          <div class="stat-value" style="color: var(--success);">${App.formatMoney(valorVentaTotal)}</div>
          <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 4px;">
            Ganancia pot.: ${App.formatMoney(valorVentaTotal - inversionTotal)}
          </div>
        </div>
      `;
    }
  },

  eliminarDePrevisualizacion(index) {
    if (index >= 0 && index < this.productosDetectados.length) {
      const removido = this.productosDetectados.splice(index, 1);
      this.renderPrevisualizacion();
      App.showToast(`Producto "${removido[0].nombre}" removido de la previsualización.`, 'info');
    }
  },

  async confirmarImportacion() {
    if (this.productosDetectados.length === 0) {
      App.showToast('No hay productos para ingresar al catálogo.', 'warning');
      return;
    }

    const modoSelect = document.getElementById('select-modo-carga-ia');
    const modo = modoSelect ? modoSelect.value : 'sumar_stock';

    const btnConfirmar = document.getElementById('btn-confirmar-carga-ia');
    if (btnConfirmar) {
      btnConfirmar.disabled = true;
      btnConfirmar.innerHTML = '<span>⏳</span><span>Ingresando al Catálogo...</span>';
    }

    try {
      const resultado = await API.bulkImportProducts({
        modo: modo,
        productos: this.productosDetectados
      });

      App.showToast(`✅ ¡Éxito! Se procesaron ${resultado.total_recibidos} productos (${resultado.total_creados} creados, ${resultado.total_actualizados} actualizados).`, 'success');

      // Limpiar área de trabajo
      this.limpiarTodo();

      // Recargar catálogo de inventario y TPV si están activos
      if (window.Inventario) window.Inventario.load();
      if (window.TPV) window.TPV.refresh();

      // Mostrar modal de confirmación o mensaje de navegación
      setTimeout(() => {
        if (confirm(`Se han guardado correctamente los productos.\n\n- Nuevos incorporados: ${resultado.total_creados}\n- Existentes actualizados: ${resultado.total_actualizados}\n\n¿Deseas ir a la pantalla de Inventario para ver el catálogo actualizado?`)) {
          App.switchTab('inventario');
        }
      }, 500);

    } catch (err) {
      console.error('Error al importar productos:', err);
      App.showToast(`Error: ${err.message || 'No se pudo completar la carga masiva.'}`, 'error');
    } finally {
      if (btnConfirmar) {
        btnConfirmar.disabled = false;
        btnConfirmar.innerHTML = '<span>🚀</span><span>Confirmar e Ingresar al Inventario</span>';
      }
    }
  }
};

window.CargaIA = CargaIA;
