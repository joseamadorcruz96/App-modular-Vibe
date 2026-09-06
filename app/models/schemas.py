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


class ProductoCreate(ProductoBase):
    """Esquema de solicitud para dar de alta un producto."""
    pass


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
    creado_en: Optional[str] = None
    actualizado_en: Optional[str] = None


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
        v_limpio = v.strip().capitalize()
        # Mapeo de acentos comunes
        if v_limpio in {"Debito", "Débito"}:
            return "Débito"
        if v_limpio in {"Credito", "Crédito"}:
            return "Crédito"
        if v_limpio not in medios_permitidos:
            raise ValueError(f"Medio de pago inválido. Permitidos: {', '.join(medios_permitidos)}")
        return v_limpio


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
