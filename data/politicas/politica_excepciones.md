# Política de excepciones y trazabilidad · AndesSupply

## Qué se considera excepción
Son excepciones: cliente en hold, línea de crédito insuficiente y monto igual o superior al monto de revisión. Toda excepción pausa el flujo hasta que Finanzas/Crédito apruebe o rechace.

## Quién decide
Las reglas objetivas las evalúa el sistema con lógica determinista. La decisión sobre una excepción la toma siempre una persona de Finanzas/Crédito; el modelo de lenguaje no aprueba ventas.

## Trazabilidad
Cada liberación registra el identificador del hilo, el cliente, el producto, la cantidad, el monto, quién aprobó y los motivos de la excepción. Repetir la aprobación del mismo hilo no duplica la liberación.
