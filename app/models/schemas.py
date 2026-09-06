"""
Módulo de Modelos Pydantic y Esquemas de Validación para CoffeePOS.

Define las estructuras de datos de entrada y salida para todos los contratos de la API REST,
garantizando sanitización de entradas, validación de rangos numéricos y tipado estricto.
"""

from typing import List, Optional, Dict
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field, ConfigDict, field_validator


# ==============================================================================
# Esquemas para Catálogo y Gestión de Productos
# ==============================================================================

class ProductoBase(BaseModel):
    """Esquema base con atributos compartidos de productos."""
    codigo: str = Field(..., min_length=1, max_length=20, description="Código único de producto (ej: CAF01)")
    nombre: str = Field(..., min_length=2, max_length=100, description="Nombre legible del producto")
    stock_inicial: int = Field(..., ge=0, description="Stock inicial asignado")
    costo_unitario: float = Field(..., ge=0.0, description="Costo de adquisición o preparación unitario")
    precio_venta: float = Field(..., ge=0.0, description="Precio de venta a público")

    @field_validator("codigo")
    @classmethod
    def normalizar_codigo(cls, v: str) -> str:
        """Normaliza el código a mayúsculas y elimina espacios circundantes."""
        return v.strip().upper()

    @field_validator("nombre")
    @classmethod
    def sanitizar_nombre(cls, v: str) -> str:
        """Limpia espacios adicionales en el nombre."""
        return v.strip()


class RecetaItemCreate(BaseModel):
    """Ingrediente individual requerido en la receta de un producto."""
    insumo_id: int = Field(..., gt=0)
    cantidad: float = Field(..., gt=0.0, description="Cantidad de insumo por 1 unidad de producto")


class ProductoCreate(ProductoBase):
    """Esquema de solicitud para dar de alta un producto."""
    receta: Optional[List[RecetaItemCreate]] = Field(None, description="Lista opcional de insumos para la receta")


class ProductoUpdate(BaseModel):
    """Esquema para actualización de campos de un producto existente."""
    codigo: Optional[str] = Field(None, min_length=1, max_length=20, description="Código único de producto")
    nombre: Optional[str] = Field(None, min_length=2, max_length=100, description="Nombre descriptivo")
    stock_inicial: Optional[int] = Field(None, ge=0, description="Stock inicial base")
    stock_actual: Optional[int] = Field(None, ge=0, description="Stock actual disponible")
    costo_unitario: Optional[float] = Field(None, ge=0.0, description="Costo unitario")
    precio_venta: Optional[float] = Field(None, ge=0.0, description="Precio de venta")
    activo: Optional[int] = Field(None, ge=0, le=1, description="Estado 1 activo / 0 inactivo")

    @field_validator("codigo")
    @classmethod
    def normalizar_codigo(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v else None

    @field_validator("nombre")
    @classmethod
    def sanitizar_nombre(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else None


class ProductoReabastecer(BaseModel):
    """Esquema para la acción de reabastecimiento rápido (+N unidades)."""
    cantidad: int = Field(..., gt=0, description="Cantidad positiva de unidades a ingresar al stock")


class ProductoResponse(ProductoBase):
    """Esquema de respuesta que incluye identificador, stock actual y estado."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_actual: int = Field(..., ge=0)
    activo: int = Field(..., ge=0, le=1)
    alerta_stock: bool = Field(False, description="True si stock_actual <= 5")
    tiene_receta: bool = Field(False, description="Indica si el producto tiene receta de insumos")
    total_insumos_receta: int = Field(0, description="Cantidad de insumos en su receta")
    creado_en: Optional[str] = None
    actualizado_en: Optional[str] = None


class ProductoBulkItem(BaseModel):
    """Ítem individual para la carga masiva/automática con IA."""
    codigo: Optional[str] = Field(None, max_length=20, description="Código único de producto (opcional, autogenerado si no se indica)")
    nombre: str = Field(..., min_length=2, max_length=100, description="Nombre legible del producto")
    stock: int = Field(0, ge=0, description="Cantidad de unidades a ingresar al inventario")
    costo_unitario: float = Field(0.0, ge=0.0, description="Costo unitario")
    precio_venta: float = Field(0.0, ge=0.0, description="Precio de venta a público")

    @field_validator("codigo")
    @classmethod
    def normalizar_codigo(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v and v.strip() else None

    @field_validator("nombre")
    @classmethod
    def sanitizar_nombre(cls, v: str) -> str:
        return v.strip()


class ProductoBulkRequest(BaseModel):
    """Solicitud de carga masiva de productos vía IA o lote."""
    modo: str = Field("sumar_stock", description="Estrategia ante existentes: 'sumar_stock' o 'solo_nuevos'")
    productos: List[ProductoBulkItem] = Field(..., min_length=1, description="Lista de productos a importar")


class ProductoBulkDetalle(BaseModel):
    """Detalle de resultado por cada producto procesado."""
    codigo: str
    nombre: str
    accion: str  # 'creado' | 'actualizado' | 'ignorado' | 'error'
    stock_previo: Optional[int] = None
    stock_final: Optional[int] = None
    costo_unitario: Optional[float] = None
    precio_venta: Optional[float] = None
    mensaje: Optional[str] = None


class ProductoBulkResponse(BaseModel):
    """Reporte de consolidación del procesamiento masivo."""
    total_recibidos: int
    total_creados: int
    total_actualizados: int
    total_ignorados: int
    detalles: List[ProductoBulkDetalle]



# ==============================================================================
# Esquemas para Toma de Pedidos, Checkout y Tickets
# ==============================================================================

class ItemPedidoCreate(BaseModel):
    """Línea de producto solicitada en el carrito."""
    producto_id: int = Field(..., gt=0, description="ID del producto en catálogo")
    cantidad: int = Field(..., gt=0, description="Unidades solicitadas (debe ser mayor a cero)")


class PedidoCreate(BaseModel):
    """Esquema de solicitud para registrar y cobrar una comanda."""
    mesa: str = Field(..., min_length=1, max_length=50, description="Identificador de mesa o Barra")
    cliente: Optional[str] = Field("Consumidor Final", max_length=100, description="Nombre o identificación del cliente")
    medio_pago: str = Field(..., description="Medio de pago: Efectivo, Débito, Crédito, Transferencia")
    items: List[ItemPedidoCreate] = Field(..., min_length=1, description="Lista de líneas del pedido")

    @field_validator("medio_pago")
    @classmethod
    def validar_medio_pago(cls, v: str) -> str:
        medios_permitidos = {"Efectivo", "Débito", "Crédito", "Transferencia"}
        v_limpio = v.strip()
        if "debito" in v_limpio.lower() or "débito" in v_limpio.lower():
            return "Débito"
        if "credito" in v_limpio.lower() or "crédito" in v_limpio.lower():
            return "Crédito"
        v_cap = v_limpio.capitalize()
        if v_cap not in medios_permitidos:
            raise ValueError(f"Medio de pago inválido. Permitidos: {', '.join(medios_permitidos)}")
        return v_cap


class ItemPedidoResponse(BaseModel):
    """Detalle de una línea de ticket emitido."""
    producto_id: int
    codigo: str
    nombre: str
    cantidad: int
    precio_unitario: float
    subtotal: float


class PedidoResponse(BaseModel):
    """Comprobante completo de un pedido procesado."""
    id: int
    numero_ticket: str
    fecha_hora: str
    mesa: str
    cliente: str
    medio_pago: str
    subtotal: float
    descuento: float
    total: float
    estado: str
    detalles: List[ItemPedidoResponse]


# ==============================================================================
# Esquemas de Configuración Operativa
# ==============================================================================

class ConfiguracionResponse(BaseModel):
    """Parámetros de configuración del sistema para la sesión actual."""
    mesas_activas: int = Field(..., ge=1, le=50)
    nombre_local: str
    moneda_simbolo: str
    formato_ticket: str


class ConfiguracionUpdate(BaseModel):
    """Esquema para ajustar la cantidad de mesas activas u otros parámetros."""
    mesas_activas: Optional[int] = Field(None, ge=1, le=50)
    nombre_local: Optional[str] = Field(None, min_length=1, max_length=100)
    formato_ticket: Optional[str] = Field(None, pattern="^(58mm|80mm)$")


# ==============================================================================
# Esquemas de Cierre de Caja y Mantenimiento
# ==============================================================================

class ProductoTopVenta(BaseModel):
    """Estadística de venta acumulada por producto."""
    nombre: str
    unidades_vendidas: int
    total_recaudado: float


class ResumenDiarioResponse(BaseModel):
    """Consolidado de ventas del día."""
    fecha: str
    total_recaudado: float
    cantidad_tickets: int
    desglose_medios_pago: Dict[str, float]
    productos_top: List[ProductoTopVenta]


class CierreCajaResponse(BaseModel):
    """Resultado de la ejecución del cierre de caja."""
    status: str
    mensaje: str
    backup_generado: str
    resumen: ResumenDiarioResponse


class ReiniciarStockRequest(BaseModel):
    """Confirmación explícita para restablecer el stock actual al valor inicial."""
    confirmar: bool = Field(..., description="Debe ser true para autorizar el reinicio de stock")


class LimpiezaTotalRequest(BaseModel):
    """Petición de formateo total con palabra de resguardo."""
    palabra_clave: str = Field(..., description="Debe ser exactamente 'borrar' para ejecutar la purga")


# ==============================================================================
# Esquemas para Insumos / Materias Primas y Recetas (Escandallo)
# ==============================================================================

class InsumoBase(BaseModel):
    """Esquema base de materia prima / insumo."""
    codigo: str = Field(..., min_length=1, max_length=20, description="Código único de insumo (ej: INS-CAFE)")
    nombre: str = Field(..., min_length=2, max_length=100, description="Nombre legible del insumo")
    unidad_medida: str = Field(..., min_length=1, max_length=20, description="Unidad: g, ml, unidad, oz, etc.")
    stock_actual: float = Field(..., ge=0.0, description="Cantidad física disponible")
    stock_minimo: float = Field(0.0, ge=0.0, description="Umbral de alerta de reabastecimiento")
    costo_unitario: float = Field(..., ge=0.0, description="Costo por unidad de medida")

    @field_validator("codigo")
    @classmethod
    def normalizar_codigo(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("nombre")
    @classmethod
    def sanitizar_nombre(cls, v: str) -> str:
        return v.strip()


class InsumoCreate(InsumoBase):
    """Esquema para crear un nuevo insumo."""
    pass


class InsumoUpdate(BaseModel):
    """Esquema para editar propiedades de un insumo."""
    codigo: Optional[str] = Field(None, min_length=1, max_length=20)
    nombre: Optional[str] = Field(None, min_length=2, max_length=100)
    unidad_medida: Optional[str] = Field(None, min_length=1, max_length=20)
    stock_actual: Optional[float] = Field(None, ge=0.0)
    stock_minimo: Optional[float] = Field(None, ge=0.0)
    costo_unitario: Optional[float] = Field(None, ge=0.0)
    activo: Optional[int] = Field(None, ge=0, le=1)

    @field_validator("codigo")
    @classmethod
    def normalizar_codigo(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v else None


class InsumoReabastecer(BaseModel):
    """Suma stock entrante a un insumo."""
    cantidad: float = Field(..., gt=0.0, description="Cantidad positiva a incorporar al inventario")


class InsumoResponse(InsumoBase):
    """Respuesta con datos de insumo y alerta de stock mínimo."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    activo: int
    alerta_stock: bool = False
    creado_en: Optional[str] = None
    actualizado_en: Optional[str] = None


class RecetaConfig(BaseModel):
    """Configuración o actualización de la receta completa de un producto."""
    ingredientes: List[RecetaItemCreate] = Field(..., min_length=1, description="Lista de insumos requeridos")


class RecetaItemResponse(BaseModel):
    """Detalle de un insumo dentro de la receta de un producto."""
    insumo_id: int
    insumo_codigo: str
    insumo_nombre: str
    unidad_medida: str
    cantidad: float
    costo_unitario_insumo: float
    costo_por_porcion: float


class RecetaDetalleResponse(BaseModel):
    """Ficha técnica de receta con análisis financiero de costos y márgenes."""
    producto_id: int
    producto_codigo: str
    producto_nombre: str
    precio_venta: float
    tiene_receta: bool
    costo_receta: float
    margen_bruto: float
    margen_porcentaje: float
    ingredientes: List[RecetaItemResponse]


# ==============================================================================
# Esquemas para Comandas de Salón (Mesas Abiertas)
# ==============================================================================

class ComandaCreate(BaseModel):
    """Apertura de comanda en una mesa."""
    mesa: str = Field(..., min_length=1, max_length=50, description="Mesa a ocupar (ej: 'Mesa 1')")
    cliente: Optional[str] = Field("Consumidor Final", max_length=100)


class ComandaItemAdd(BaseModel):
    """Adición de producto(s) a una comanda abierta."""
    producto_id: int = Field(..., gt=0)
    cantidad: int = Field(..., gt=0)
    notas: Optional[str] = Field(None, max_length=200, description="Observaciones (ej. 'sin azúcar')")


class ComandaItemBatchAdd(BaseModel):
    """Ronda de múltiples productos a incorporar a una mesa."""
    items: List[ComandaItemAdd] = Field(..., min_length=1)


class ComandaItemResponse(BaseModel):
    """
    Línea de consumo acumulada en una mesa.
    Incorpora estado del ítem ('En preparación' / 'Servido' / 'Cancelado')
    y bandera de 'descontado_stock' para saber si ya descontó existencias en barra/cocina.
    """
    id: int
    producto_id: int
    codigo: str
    nombre: str
    cantidad: int
    precio_unitario: float
    subtotal: float
    notas: Optional[str] = None
    estado: str = "En preparación"
    descontado_stock: int = 0
    creado_en: Optional[str] = None
    servido_en: Optional[str] = None


class ComandaResponse(BaseModel):
    """Estado y detalle de una comanda de salón."""
    id: int
    numero_comanda: str
    mesa: str
    cliente: str
    estado: str
    subtotal: float
    total_items: int
    creado_en: Optional[str] = None
    detalles: List[ComandaItemResponse]


class MesaEstadoResponse(BaseModel):
    """Resumen de ocupación para la grilla del salón en el TPV."""
    mesa: str
    ocupada: bool
    comanda_id: Optional[int] = None
    numero_comanda: Optional[str] = None
    estado: Optional[str] = None
    subtotal: float = 0.0
    cliente: Optional[str] = None
    items_count: int = 0
    tiempo_abierta: Optional[str] = None


class ComandaCheckout(BaseModel):
    """Liquidación y cobro de una comanda abierta."""
    medio_pago: str = Field(..., description="Efectivo, Débito, Crédito o Transferencia")
    descuento: float = Field(0.0, ge=0.0)

    @field_validator("medio_pago")
    @classmethod
    def validar_medio_pago(cls, v: str) -> str:
        medios = {"Efectivo", "Débito", "Crédito", "Transferencia"}
        v_limpio = v.strip()
        if "debito" in v_limpio.lower() or "débito" in v_limpio.lower():
            return "Débito"
        if "credito" in v_limpio.lower() or "crédito" in v_limpio.lower():
            return "Crédito"
        v_cap = v_limpio.capitalize()
        if v_cap not in medios:
            raise ValueError(f"Medio de pago inválido. Permitidos: {', '.join(medios)}")
        return v_cap


class ComandaCancelRequest(BaseModel):
    """
    Petición para cancelar una comanda o ítem servido.
    Permite decidir explícitamente si se repone el inventario o se asume como merma/desperdicio.
    """
    restaurar_stock: bool = Field(False, description="True para restituir inventario; False para registrar merma sin reponer")


# ==============================================================================
# Esquemas para Auditoría Detallada en Cierre de Caja
# ==============================================================================

class AuditoriaItemVenta(BaseModel):
    """Desglose de cada producto consumido dentro de una comanda o pedido."""
    producto_id: int
    codigo: str
    nombre: str
    cantidad: int
    precio_unitario: float
    subtotal: float


class AuditoriaComandaVenta(BaseModel):
    """Fila de auditoría para cada transacción/comanda cerrada durante la jornada."""
    ticket_id: int
    numero_ticket: str
    comanda_id: Optional[int] = None
    numero_comanda: Optional[str] = None
    mesa: str
    cliente: str
    medio_pago: str
    fecha_hora: str
    total: float
    items: List[AuditoriaItemVenta]


class AuditoriaJornadaResponse(BaseModel):
    """Informe consolidado tipo tabla con todas las comandas, productos, pagos y medios de pago."""
    fecha: str
    total_recaudado: float
    cantidad_tickets: int
    desglose_medios_pago: Dict[str, float]
    pedidos: List[AuditoriaComandaVenta]

