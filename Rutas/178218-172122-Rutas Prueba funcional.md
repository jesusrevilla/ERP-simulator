Precondiciones
Hoja de ruta RUTA-GAMING-PC en estatus LIBERADA (creada por INGENIERO_PROCESOS y aprobada por JEFE_PRODUCCION), con 
3 etapas correlativas: Etapa_1_Base (90 min), Etapa_2_Energia (60 min) y Etapa_3_Graficos (60 min).

Existencias suficientes en ALM-01 para los 6 componentes (Motherboard_B650, CPU_Ryzen7, RAM_16GB_DDR5, SSD_1TB_NVMe, 
PowerSupply_750W, GraphicsCard_RTX) y stock disponible de PowerSupply_750W en ALM-02.

Pasos de ejecución
1-Crear la Orden de Producción OP-001 para fabricar 2 Gaming_PC tomando RUTA-GAMING-PC dentro de un horizonte de 
fechas válido y cambiar su estatus de PLANIFICADA a LIBERADA.

2-Intentar despachar PowerSupply_750W (Etapa 2) antes de emitir los materiales de la Etapa 1 para comprobar el bloqueo 
secuencial.

3-Filtrar el despacho (Issue for Production) por Etapa_1_Base, emitir sus 4 componentes desde ALM-01 y, acto seguido, 
intentar borrar la Etapa 1 de la orden liberada.

4-Cambiar el almacén de Etapa_2_Energia a ALM-02 y despachar PowerSupply_750W; después despachar GraphicsCard_RTX en 
Etapa_3_Graficos desde ALM-01.

5-Finalizar la orden (CERRADA), ejecutar la auditoría de costos y validar el evento JSON ISA-95 
generado.   

Resultados esperados
-La orden conserva una copia independiente de la ruta (210 min totales) con fechas de etapa dentro del horizonte definido 
y sin líneas huérfanas.

-El sistema rechaza el despacho anticipado de la Etapa 2 y bloquea la eliminación de la Etapa 1 al tener movimientos 
registrados.

-El stock se descuenta exactamente por etapa y almacén (ALM-01 en Etapas 1 y 3; ALM-02 en Etapa 2) 
sin afectar otros almacenes.

-Al cerrar la orden, el costo real coincide con el costo planificado ($2,330; diferencia = 0).

-El JSON ISA-95 (OperationsResponse) se emite en estado Completed, incluyendo los 3 SegmentResponse con sus
ActualStartTime / ActualEndTime cronológicos, los materiales consumidos (MaterialActual) y el producto terminado
(MaterialProducedActual = Gaming_PC). 
