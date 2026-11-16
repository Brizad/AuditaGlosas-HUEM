"""Valores fijos que comparten la base de datos, el motor de reglas y la API."""

# Tipos de lote. «linea_base» y «piloto» sirven para comparar el antes y el después (HU-07).
TIPO_GENERAL = "general"
TIPO_LINEA_BASE = "linea_base"
TIPO_PILOTO = "piloto"
TIPOS_LOTE = (TIPO_GENERAL, TIPO_LINEA_BASE, TIPO_PILOTO)

# Estados de un lote.
ESTADO_LOTE_CARGADO = "cargado"
ESTADO_LOTE_VALIDADO = "validado"

# Estados de una factura.
ESTADO_SIN_VALIDAR = "sin_validar"
ESTADO_APTA = "apta"
ESTADO_CON_INCONSISTENCIAS = "con_inconsistencias"

# Clases de servicio que se leen del RIPS (Res. 2275 de 2023).
CLASE_CONSULTA = "consulta"
CLASE_PROCEDIMIENTO = "procedimiento"
CLASE_MEDICAMENTO = "medicamento"
