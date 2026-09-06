# 🤖 Guía de Carga Automática de Productos con IA (Coffee SoKa)

Esta guía te explica cómo utilizar cualquier Inteligencia Artificial (ChatGPT, Claude, Gemini, o el chat de IA que uses) para ingresar o actualizar productos en Coffee SoKa en menos de 1 minuto, **sin necesidad de saber nada de informática**.

---

## 🎯 ¿Cómo funciona el proceso?

```
[1. Copiar Instrucción] ➡️ [2. Pegar en tu IA + Foto o Lista] ➡️ [3. Pegar en Coffee SoKa y Confirmar]
```

---

## 📋 1. Instrucción Maestra para la IA (Copia y Pega)

Copia este texto exacto y pégalo en tu IA favorita:

```text
Actúa como un asistente administrativo experto para la cafetería "Coffee SoKa".
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
[PEGA AQUÍ TU LISTA, FOTO DE FACTURA O NOTA DE VOZ]
```

---

## 📸 2. Ejemplos de lo que le puedes mandar a la IA

La IA entenderá cualquiera de estos formatos:

### Ejemplo A: Foto de una Factura o Remito
> Simplemente adjunta la foto en la app de ChatGPT o Gemini junto con la instrucción copiada.

### Ejemplo B: Una Nota de Voz o Texto Desordenado
> *"Hoy llegaron 30 medialunas de manteca a 400 pesos cada una, para vender a 1000. También 10 tortas de ricota que nos costaron 1200 y las vendemos a 2800, y 5 bolsas de café colombia de kilo a 4000 para vender a 9500."*

### Ejemplo C: Un Mensaje de WhatsApp del Proveedor
> *Proveedor Panadería:*
> *24 Medialunas manteca $450*
> *12 Medialunas grasa $450*
> *8 Tartas de manzana $900*
> *15 Alfajores de maicena $600*

---

## 📊 3. Resultado que te entregará la IA

La IA responderá con una tabla limpia como esta:

| Codigo | Nombre | Stock | Costo | Precio |
| :--- | :--- | :--- | :--- | :--- |
| MED01 | Medialuna de Manteca | 24 | 450 | 1200 |
| MED02 | Medialuna de Grasa | 12 | 450 | 1200 |
| TAR01 | Tarta de Manzana Porción | 8 | 900 | 2500 |
| ALF01 | Alfajor de Maicena Artesanal | 15 | 600 | 1500 |

---

## 🚀 4. Ingreso en Coffee SoKa

1. En Coffee SoKa, haz clic en la pestaña **🤖 Carga con IA**.
2. **Pega la tabla** en el recuadro grande (o arrastra el archivo `.md`).
3. Haz clic en **🔍 Interpretar y Previsualizar**.
4. Verás la lista con sus márgenes calculados y avisos:
   - 🟢 **Nuevo Producto:** Se agregará al catálogo con su código correspondiente.
   - 🟡 **Sumar a Existente:** Si el producto ya existía, sumará las unidades al stock actual sin borrar el historial.
5. Presiona **🚀 Confirmar e Ingresar al Inventario**. ¡Y listo! Los productos ya están disponibles para vender en la comandera y el TPV.
