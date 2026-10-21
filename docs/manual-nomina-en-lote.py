# -*- coding: utf-8 -*-
"""Manual de uso: nómina mensual en lote (MRO Energy Group, Odoo 18)."""
import sys
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

OUT = sys.argv[1]
NAVY = colors.HexColor("#1F3864")
GREY = colors.HexColor("#555555")
LIGHT = colors.HexColor("#EEF3FA")

ss = getSampleStyleSheet()
H0 = ParagraphStyle("H0", parent=ss["Title"], fontSize=22, textColor=NAVY, spaceAfter=4, alignment=TA_CENTER)
SUB = ParagraphStyle("SUB", parent=ss["Normal"], fontSize=11, textColor=GREY, alignment=TA_CENTER, spaceAfter=18)
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=15, textColor=NAVY, spaceBefore=14, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=12, textColor=NAVY, spaceBefore=10, spaceAfter=4)
P = ParagraphStyle("P", parent=ss["Normal"], fontSize=10, leading=14, spaceAfter=6)
STEP = ParagraphStyle("STEP", parent=P, leftIndent=14, bulletIndent=0)
NOTE = ParagraphStyle("NOTE", parent=P, backColor=LIGHT, borderPadding=6, leftIndent=6, rightIndent=6, spaceBefore=4, spaceAfter=10)
SMALL = ParagraphStyle("SMALL", parent=P, fontSize=8.5, textColor=GREY)


def p(t, st=P):
    return Paragraph(t, st)


def steps(items):
    return [Paragraph("<b>%d.</b> %s" % (i, t), STEP) for i, t in enumerate(items, 1)]


def table(rows, widths):
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BFBFBF")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def cell(t):
    return Paragraph(t, ParagraphStyle("c", parent=P, fontSize=9, leading=12, spaceAfter=0))


story = []
story += [
    Spacer(1, 2 * cm),
    p("Nómina mensual en lote", H0),
    p("Guía de uso del módulo de Nómina Guatemala en Odoo 18 - MRO Energy Group", SUB),
    p("Esta guía explica cómo hacer la nómina de todos los empleados de una vez, desde el "
      "<b>lote</b>, en lugar de recibo por recibo. El trabajo del mes queda en seis pasos: "
      "crear el lote, generar los recibos, capturar las novedades, calcular y confirmar, "
      "pagar las quincenas y sacar los reportes."),
    p("<b>Regla de oro:</b> todo se hace desde el lote. Solo se abre un recibo individual "
      "para capturar algo de ese empleado (horas extra, una bonificación, faltas, vacaciones) "
      "o para revisar su cálculo.", NOTE),
]

# --- Resumen
story += [p("El mes en una página", H1)]
story.append(table([
    [cell("<b>Paso</b>"), cell("<b>Dónde</b>"), cell("<b>Qué hacer</b>")],
    [cell("1. Crear el lote"), cell("Nómina > Recibos de nómina > Lotes > Nuevo"),
     cell("Nombre (p. ej. OCTUBRE 2026), fecha inicio 01 y fin último día del mes. Guardar.")],
    [cell("2. Generar recibos"), cell("Botón <b>Generar recibos de nómina</b> del lote"),
     cell("Deja marcados todos los empleados y pulsa Generar. Se crean y calculan los recibos de todos.")],
    [cell("3. Novedades"), cell("Recibo del empleado > pestaña Cálculo del salario"),
     cell("Solo para quien tenga: horas extra, bonificación, comisión, descuento, vacaciones pagadas. Faltas y vacaciones gozadas en Días trabajados.")],
    [cell("4. Calcular y confirmar"), cell("Botones <b>Calcular nómina</b> y <b>Confirmar</b> del lote"),
     cell("Calcular recalcula todos. Revisar el Excel. Confirmar cierra el cálculo de todos los recibos.")],
    [cell("5. Pagar"), cell("Botones <b>Marcar pagada 1ª quincena</b> / <b>2ª quincena</b> del lote"),
     cell("Al entregar cada quincena, un solo clic marca el pago de todos los empleados.")],
    [cell("6. Reportes"), cell("Engrane del lote > Imprimir"),
     cell("Nómina de sueldos y salarios (Excel), boletas y comprobantes.")],
], [3.3 * cm, 5.2 * cm, 8.5 * cm]))
story.append(PageBreak())

# --- Antes de empezar
story += [p("Antes del primer lote del mes", H1),
          p("Estas cosas se revisan una vez; si no cambian, no hay que tocarlas cada mes.")]
story += steps([
    "<b>Empleados nuevos:</b> cada empleado necesita un <b>contrato</b> en estado <i>En proceso</i> "
    "con fecha de inicio, salario mensual, bonificación incentivo (Q250), frecuencia de pago "
    "<i>Quincenal</i> y el tipo de nómina <i>Nómina Mensual (Guatemala)</i>. Sin contrato, el "
    "empleado no aparece al generar los recibos.",
    "<b>Datos del empleado:</b> DPI y número de afiliación IGSS (pestaña Guatemala de la ficha). "
    "El DPI sale en la nómina de sueldos y salarios.",
    "<b>Bajas:</b> si alguien se retiró, hazle su <b>finiquito</b> (recibo con la casilla "
    "<i>Recibo de liquidación</i>) y cierra el contrato. Un empleado con contrato cerrado y sin "
    "finiquito queda en el aire.",
    "<b>Firmas de la nómina:</b> Ajustes > Empresas > MRO ENERGY GROUP > pestaña <i>Nómina GT</i>: "
    "quién elabora y quién aprueba. Salen al pie del Excel.",
])

# --- Paso 1
story += [p("Paso 1. Crear el lote del mes", H1)]
story += steps([
    "Ve a <b>Nómina > Recibos de nómina > Lotes</b> y pulsa <b>Nuevo</b>.",
    "Nombre: el mes y el año (por ejemplo <b>OCTUBRE 2026</b>).",
    "Fechas: del <b>día 1</b> al <b>último día del mes</b>. El cálculo de IGSS e ISR es siempre "
    "mensual; el pago en quincenas se maneja aparte (paso 5).",
    "Guarda. Solo puede existir un lote por mes.",
])

# --- Paso 2
story += [p("Paso 2. Generar los recibos de todos", H1)]
story += steps([
    "En el lote, pulsa <b>Generar recibos de nómina</b>.",
    "Se abre una ventana con la lista de empleados que tienen contrato vigente en el mes. "
    "Vienen <b>todos marcados</b>; quita solo a quien no deba ir en esta nómina.",
    "Pulsa <b>Generar</b>. Odoo crea un recibo por empleado y lo calcula con su salario, "
    "bonificación incentivo, IGSS e ISR.",
    "Ya están todos los recibos. No hace falta abrir ninguno salvo para capturar novedades.",
])
story.append(p("Si un empleado no aparece en la lista, es porque no tiene contrato en estado "
               "<i>En proceso</i> con fechas dentro del mes. Corrige el contrato y vuelve a pulsar "
               "Generar recibos (solo crea los que falten).", NOTE))

# --- Paso 3
story += [p("Paso 3. Capturar novedades (solo donde las haya)", H1),
          p("Las novedades son lo que cambia respecto a un mes normal. Se capturan en el recibo "
            "del empleado, <b>todo en la misma tabla</b> de la pestaña <b>Cálculo del salario</b>. "
            "Al guardar, el recibo se recalcula solo.")]
story.append(table([
    [cell("<b>Novedad</b>"), cell("<b>Cómo se captura</b>")],
    [cell("Horas extra diurnas / nocturnas"),
     cell("Pulsa <i>Agregar una línea</i>, elige <b>Horas extra diurnas</b> (o nocturnas) y escribe las <b>horas</b> en la columna <b>Cantidad</b>. El sistema calcula el monto (salario / 240 x 1.5 o x 2).")],
    [cell("Bonificación adicional, comisión"),
     cell("<i>Agregar una línea</i>, elige el concepto y escribe el monto en <b>Total</b>.")],
    [cell("Otras deducciones (uniforme, préstamo externo...)"),
     cell("<i>Agregar una línea</i>, elige <b>Otras deducciones</b> y escribe el monto <b>en negativo</b> en Total (p. ej. -150).")],
    [cell("Vacaciones pagadas en dinero"),
     cell("<i>Agregar una línea</i>, elige <b>Vacaciones pagadas</b> y escribe los <b>días</b> en Cantidad. Paga días x sueldo diario y descuenta del saldo de vacaciones.")],
    [cell("Vacaciones gozadas (descanso)"),
     cell("Pestaña <b>Días trabajados y entradas</b>, campo <b>Días gozados</b>. No cambian el salario; solo bajan el saldo de días.")],
    [cell("Faltas sin goce"),
     cell("Pestaña <b>Días trabajados y entradas</b>, campo <b>Faltas / días no pagados</b>. Descuenta salario / 30 por día. Después pulsa <b>Calcular hoja</b> o usa Calcular nómina en el lote.")],
    [cell("Corregir el ISR u otro concepto"),
     cell("Edita directamente el <b>Total</b> de la línea en la tabla (deducciones en negativo). Queda marcado <i>(ajuste manual)</i> y en el historial, y el neto se recalcula. Para deshacerlo, borra la fila del <i>Historial de ajustes manuales</i>.")],
], [5 * cm, 12 * cm]))
story.append(p("Para quitar una novedad usa la papelera de la fila. Los subtotales (Sueldo imponible y "
               "Salario neto) no se editan: se corrigen los conceptos que los forman.", SMALL))

# --- Paso 4
story += [p("Paso 4. Calcular y confirmar el lote", H1)]
story += steps([
    "En el lote, pulsa <b>Calcular nómina</b>. Recalcula todos los recibos con las novedades "
    "capturadas. Se puede pulsar las veces que haga falta.",
    "Revisa: engrane del lote > <b>Imprimir > Nómina de sueldos y salarios (Excel)</b>. Es la "
    "planilla completa con quincenas, IGSS, ISR y líquido de cada empleado.",
    "Si algo no cuadra, corrige en el recibo (paso 3) y vuelve a Calcular nómina.",
    "Pulsa <b>Confirmar</b>. Todos los recibos pasan a <i>Hecho</i>: el cálculo queda fijo, el ISR "
    "retenido se registra para la proyección anual y se crea la programación de pagos de cada "
    "empleado (sus dos quincenas).",
])
story.append(p("Después de confirmar no se puede editar un recibo. Si hay que corregir uno, ábrelo, "
               "pulsa <b>Cancelar</b> y luego <b>Volver a borrador</b>, corrige, calcula y confírmalo "
               "de nuevo desde el propio recibo.", NOTE))

# --- Paso 5
story += [p("Paso 5. Pagar las quincenas", H1),
          p("Cada recibo lleva su <b>estado de cuenta</b>: el líquido del mes dividido en primera y "
            "segunda quincena (el monto de la primera es el fijado en el contrato de cada empleado). "
            "Ya no hay que entrar a cada recibo a marcar el pago:")]
story += steps([
    "Cuando pagues la primera quincena, en el lote pulsa <b>Marcar pagada 1ª quincena</b>. "
    "Se marca como pagada en todos los recibos del lote de una vez.",
    "A fin de mes, pulsa <b>Marcar pagada 2ª quincena</b>.",
    "El estado de pago de cada recibo (Sin pagar / Parcial / Pagado) y el saldo pendiente se "
    "actualizan solos. Se ven en el recibo (pestaña Estado de cuenta / Pagos) y desde el "
    "contrato del empleado con el botón <b>Periodos</b>.",
    "Para un pago distinto en un solo empleado (adelanto, pago parcial), ábrelo y edítalo en su "
    "pestaña <b>Estado de cuenta / Pagos</b>; el botón del lote solo toca lo que esté pendiente.",
])
story.append(p("El comprobante de pago para firma se imprime desde la línea de pago del recibo "
               "(botón Comprobante). La boleta de pago del mes, desde el recibo: Imprimir > Boleta.", SMALL))

# --- Paso 6
story += [p("Paso 6. Reportes y cierre", H1)]
story.append(table([
    [cell("<b>Reporte</b>"), cell("<b>Dónde</b>"), cell("<b>Para qué</b>")],
    [cell("Nómina de sueldos y salarios (Excel)"), cell("Lote > engrane > Imprimir"), cell("La planilla del mes en el formato de la empresa, con firmas.")],
    [cell("Planilla IGSS, Costos de personal"), cell("Lote > engrane > Imprimir"), cell("Base IGSS por empleado, cuotas laboral y patronal; costo total.")],
    [cell("Libro de Salarios, Informe del Empleador"), cell("Lote > engrane > Imprimir"), cell("Reportes anuales por trabajador (MinTrab).")],
    [cell("Boleta de pago, Comprobante de pago"), cell("Recibo > Imprimir"), cell("Para entregar y firmar.")],
    [cell("Control de vacaciones, Pasivo laboral"), cell("Empleados > Imprimir"), cell("Días pendientes; aguinaldo, bono 14 e indemnización acumulados.")],
], [5.2 * cm, 4.3 * cm, 7.5 * cm]))
story.append(p("Los reportes en PDF requieren que el servidor tenga instalado el componente de "
               "impresión (wkhtmltopdf); el Excel funciona siempre.", SMALL))
story += [p("Cerrar el período", H2)]
story += steps([
    "<b>Contabilizar</b> (responsable de nómina): marca el lote como contabilizado. La póliza "
    "contable se genera con <b>Generar póliza contable</b> una vez que las reglas tengan cuentas "
    "asignadas (Configuración > Cuentas contables).",
    "<b>Cerrar período</b>: ya no se pueden tocar los recibos. Si hace falta, <b>Reabrir</b> "
    "(solo responsable).",
])

# --- Casos especiales
story.append(PageBreak())
story += [p("Casos especiales", H1)]
story += [p("Empleado que entra o sale a mitad de mes", H2),
          p("No hay que hacer nada especial: el recibo calcula los días proporcionales (salario / 30 "
            "por día) según las fechas del contrato. Si entró después del 15, todo su líquido queda "
            "en la segunda quincena. El ISR también se proyecta solo desde su fecha de ingreso.")]
story += [p("Empleado que se retira (finiquito)", H2)]
story += steps([
    "Crea un recibo individual para el empleado con fecha fin = fecha de retiro y marca "
    "<b>Recibo de liquidación (finiquito)</b>.",
    "Indica el motivo de finalización y pulsa <b>Calcular finiquito</b>: agrega aguinaldo y bono 14 "
    "proporcionales, vacaciones pendientes e indemnización si corresponde.",
    "Confirma el recibo: cierra el contrato y archiva al empleado.",
])
story += [p("ISR: cómo funciona y cuándo tocarlo", H2),
          p("El sistema proyecta la renta anual de cada empleado <b>desde su fecha de ingreso</b> con "
            "su salario, resta la deducción personal e IGSS, calcula el impuesto del año y lo reparte "
            "entre los meses que faltan. Cada mes descuenta lo ya retenido. Para la mayoría de los "
            "sueldos el resultado es cero. Solo si el contador indica otra retención, se edita el "
            "Total de <i>Retención ISR</i> en la tabla del recibo; la proyección lo toma en cuenta en "
            "los meses siguientes. La proyección se consulta en Nómina > ISR > Proyecciones.")]
story += [p("Anticipos y préstamos", H2),
          p("Se registran en Nómina > Anticipos. Un anticipo entregado se recupera en el recibo del "
            "mes como línea de recuperación y las quincenas pendientes se ajustan solas.")]

# --- Preguntas frecuentes
story += [p("Preguntas frecuentes", H1)]
faq = [
    ("Pulsé Generar recibos y no salió ningún empleado.",
     "Ningún empleado tiene contrato vigente con fechas dentro del lote. Revisa los contratos (estado En proceso, fecha de inicio)."),
    ("Un recibo quedó En espera dentro de un lote ya confirmado.",
     "Ábrelo y pulsa Confirmar en el propio recibo; o vuelve a pulsar Confirmar en el lote, que confirma los pendientes."),
    ("No aparece el botón Marcar pagada 1ª quincena.",
     "Aparece solo cuando el lote está confirmado y hay quincenas pendientes. Si no hay programación de pagos, usa primero Generar programación de pagos."),
    ("La sección Otras entradas del recibo está vacía.",
     "Es normal: las novedades ya se capturan en la tabla de Cálculo del salario (paso 3)."),
    ("Quiero deshacer un ajuste manual.",
     "En el recibo, borra la fila del Historial de ajustes manuales (debajo de la tabla) o vuelve a escribir el valor calculado. El recibo se recalcula."),
    ("Las vacaciones gozadas no cambian el salario, ¿es correcto?",
     "Sí. Son descanso pagado: el sueldo se paga completo y solo baja el saldo de días. Las vacaciones pagadas en dinero sí generan una línea."),
]
rows = [[cell("<b>Situación</b>"), cell("<b>Qué hacer</b>")]] + [[cell(q), cell(a)] for q, a in faq]
story.append(table(rows, [6 * cm, 11 * cm]))


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(2 * cm, 1.2 * cm, "Nómina Guatemala para Odoo 18 - Guía de uso en lote - octubre 2026")
    canvas.drawRightString(letter[0] - 2 * cm, 1.2 * cm, "Página %d" % doc.page)
    canvas.restoreState()


doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=2 * cm, rightMargin=2 * cm,
                        topMargin=1.8 * cm, bottomMargin=2 * cm,
                        title="Nómina mensual en lote - Guía de uso",
                        author="Olive GT", subject="Módulo de Nómina Guatemala, Odoo 18")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("OK", OUT)
