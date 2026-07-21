# Plan técnico — Módulo de Nómina Guatemala sobre Odoo 18 Enterprise

> Base: **Odoo 18 Enterprise `hr_payroll`**
> Referencia funcional: *Diseño Funcional de Módulo de Nómina v1.0* (José Enrique Barrios, Julio 2026)
> Alcance: implementación de la nómina guatemalteca (IGSS, ISR asalariados, Aguinaldo, Bono 14, Bonificación Incentivo, indemnización, liquidaciones, reportes legales) como capa de localización sobre el motor de nómina de Odoo.

---

## 0. Estrategia general

El motor `hr_payroll` de Odoo 18 Enterprise ya resuelve el 70% del proceso descrito en el capítulo 2 del diseño funcional (períodos, cálculo por reglas, contabilización, boletas). **No reimplementamos el motor**; construimos una **localización `l10n_gt_*`** que aporta:

1. Los datos maestros guatemaltecos del empleado/contrato (DPI, NIT, IGSS, circunscripción).
2. Las **reglas salariales** (`hr.salary.rule`) con la aritmética de GT.
3. Los **parámetros legales** versionados por fecha (`hr.rule.parameter`).
4. Los **procesos que Odoo no tiene**: proyección ISR anual, liquidación/indemnización, planillas de Aguinaldo/Bono 14.
5. Los **reportes legales** (Libro de Salarios, Informe del Empleador, planilla IGSS).

### Mapeo de conceptos: diseño funcional → Odoo 18

| Concepto del diseño | Objeto Odoo 18 Enterprise |
|---|---|
| Tipo de nómina (§1.4.1) | `hr.payroll.structure.type` |
| Estructura de cálculo | `hr.payroll.structure` |
| Concepto de ingreso/deducción (§1.4.2/3) | `hr.salary.rule` (+ `hr.salary.rule.category`) |
| Parámetros legales (§1.4.4) | `hr.rule.parameter` + `hr.rule.parameter.value` (por fecha) |
| Período de nómina (§3.2) | `hr.payslip.run` (lote) |
| Cálculo de nómina / recibo (§3.3) | `hr.payslip` + `hr.payslip.line` |
| Novedades (§2.4) | `hr.payslip.input` (+ `hr.payslip.input.type`) y `hr.work.entry` |
| Días/horas trabajadas | `hr.work.entry` + `hr.work.entry.type` |
| Historial de contratos (§3.1.6) | versionado de `hr.contract` (`hr.version` en 18) |
| Calendarios laborales (§1.4.5) | `resource.calendar` |
| Póliza contable (§2.9) | `account.move` vinculado al payslip |

> **Nota de versión Odoo 18:** en 18.0 el contrato pasó a un modelo de *versiones* del empleado (`hr.version`), y el salario/estructura viven en la versión vigente. Toda referencia a "contrato vigente" del diseño se resuelve con la versión activa a la fecha del período. Los cálculos históricos (aguinaldo, indemnización) leen las versiones por rango de fechas.

---

## 1. Árbol de módulos

```
l10n_gt_hr
    Extiende hr.employee y hr.version (contrato) con los campos GT.
    Salarios mínimos por circunscripción económica y su validación.
    Depende de: hr, hr_contract

l10n_gt_payroll
    Categorías, reglas salariales y estructuras de la nómina ordinaria GT.
    Parámetros legales (IGSS, bonificación incentivo, tipos de hora extra).
    Depende de: l10n_gt_hr, hr_payroll, hr_work_entry_contract

l10n_gt_payroll_isr
    Proyección anual de ISR asalariados y su retención mensual.
    Depende de: l10n_gt_payroll

l10n_gt_payroll_prestaciones
    Aguinaldo, Bono 14, control de vacaciones, planillas independientes.
    Depende de: l10n_gt_payroll

l10n_gt_payroll_liquidacion
    Liquidaciones laborales, indemnización, finiquito.
    Depende de: l10n_gt_payroll_prestaciones

l10n_gt_payroll_loans
    Préstamos y anticipos con plan de cuotas y descuento automático.
    Depende de: l10n_gt_payroll

l10n_gt_payroll_account
    Cuentas contables por concepto, generación de póliza, reporte de póliza
    independiente (para clientes sin contabilidad Odoo).
    Depende de: l10n_gt_payroll, account

l10n_gt_payroll_report
    Boleta, planilla general, Libro de Salarios, Informe del Empleador,
    reportes de IGSS/ISR/costos de personal.
    Depende de: l10n_gt_payroll_prestaciones, l10n_gt_payroll_isr
```

Separación justificada por el propio diseño: §6.9 pide poder generar la póliza sin usar Contabilidad de Odoo, y §1.3 pide vender "nómina" de forma modular.

---

## 2. `l10n_gt_hr` — datos maestros

### 2.1 `hr.employee` (campos añadidos)

Cubre §3.1.1–3.1.4 y los campos del Informe del Empleador (§6.15) que hoy no existen.

| Campo | Tipo | Notas |
|---|---|---|
| `l10n_gt_dpi` | Char | DPI, 13 dígitos, con validación de formato y unicidad |
| `l10n_gt_nit` | Char | NIT, validación de dígito verificador |
| `l10n_gt_first_name` / `middle_name` / `third_name` | Char | Nombres separados (Informe del Empleador los exige separados) |
| `l10n_gt_first_surname` / `second_surname` / `married_surname` | Char | Apellidos separados |
| `l10n_gt_igss_affiliation` | Char | Número de afiliación IGSS |
| `l10n_gt_igss_applies` | Boolean | Afecto a IGSS |
| `l10n_gt_isr_applies` | Boolean | Sujeto a retención ISR |
| `l10n_gt_academic_level` | Selection | Código MinTrab (nivel académico) |
| `l10n_gt_ethnic_group` | Selection | Pueblo de pertenencia (código MinTrab) |
| `l10n_gt_disability_type` | Selection | Código MinTrab |
| `l10n_gt_children_count` | Integer | Cantidad de hijos |
| `l10n_gt_profession` | Char | Título o diploma |

Los `Selection` con "código MinTrab" se cargan como `ir.model.fields.selection` o tablas `l10n.gt.catalog.*` con el código exacto de la nomenclatura del Ministerio de Trabajo (anexo 8.4 muestra códigos como país `GTM`, nivel `10`, pueblo `99`, etc.).

### 2.2 `hr.version` / contrato (campos añadidos)

Cubre §3.1.3 (información salarial) y §3.1.6 (historial):

| Campo | Tipo | Notas |
|---|---|---|
| `l10n_gt_salary_type` | Selection | mensual / diario / por hora |
| `l10n_gt_bonif_incentivo` | Monetary | Bonificación Incentivo pactada (default Q250) |
| `l10n_gt_economic_zone` | Many2one → `l10n.gt.economic.zone` | Circunscripción económica |
| `l10n_gt_excluir_horas_extra` | Boolean | §4.3.4 excluir del cálculo de HE |
| `l10n_gt_contract_pdf` | Binary/attachment | §3.1.6 resguardo del contrato firmado |

**Historial de contratos (§3.1.6):** en Odoo 18 cada cambio de salario/puesto/jornada crea una nueva `hr.version` con `date_version`. Activamos `_track` sobre los campos salariales para el log de auditoría (usuario + fecha/hora). El "reporte histórico de contratos" (§6.11) es una vista lista sobre `hr.version`.

### 2.3 Salario mínimo por circunscripción (§4.1.4, §7.3)

```
l10n.gt.economic.zone         → catálogo de circunscripciones
l10n.gt.minimum.wage          → (zone, date_from, amount)  versionado por fecha
```

Constraint en `hr.version`: al guardar, `salary_diario >= minimo_vigente(zone, date_version)`. Mensaje claro al usuario (§7.8).

---

## 3. `l10n_gt_payroll` — reglas y estructuras

### 3.1 Parámetros legales (`hr.rule.parameter`)

Todo lo configurable de §7.3, versionado por fecha (así el recálculo histórico usa el valor vigente del período):

| `code` | Valor inicial (2026) | Uso |
|---|---|---|
| `l10n_gt_igss_laboral` | 0.0483 | IGSS laboral §4.9 |
| `l10n_gt_igss_patronal` | 0.1267 | IGSS patronal §4.15 (10.67 + IRTRA 1 + INTECAP 1) |
| `l10n_gt_igss_patronal_igss` | 0.1067 | desglose para reportes |
| `l10n_gt_igss_patronal_irtra` | 0.01 | |
| `l10n_gt_igss_patronal_intecap` | 0.01 | |
| `l10n_gt_bonif_incentivo_min` | 250.00 | mínimo legal §4.2.4 |
| `l10n_gt_isr_deduccion_personal` | 51024.00 | gastos personales sin comprobación §4.10 |
| `l10n_gt_isr_tramo1_tasa` | 0.05 | hasta Q300,000 |
| `l10n_gt_isr_tramo2_limite` | 300000.00 | |
| `l10n_gt_isr_tramo2_fijo` | 15000.00 | importe fijo |
| `l10n_gt_isr_tramo2_tasa` | 0.07 | excedente |
| `l10n_gt_he_diurna_factor` | 1.5 | §4.3.2 |
| `l10n_gt_he_nocturna_factor` | 2.0 | §4.3.2 |

### 3.2 Categorías de reglas (`hr.salary.rule.category`)

`BASIC`, `ALW` (asignaciones/ingresos), `DED` (deducciones), `COMP` (aportes patronales/costo empresa), `NET`. Añadimos categorías GT: `GT_PREST` (prestaciones), `GT_PATRONAL`.

### 3.3 Reglas salariales (capítulo 4 del diseño)

Cada regla lleva flags custom que agregamos a `hr.salary.rule`:

- `l10n_gt_afecto_igss` (Boolean) — entra a la base IGSS.
- `l10n_gt_afecto_isr` (Boolean) — entra a la proyección ISR.
- `l10n_gt_es_ordinario` (Boolean) — forma parte del salario ordinario (base de prestaciones).

Tabla de reglas de la estructura ordinaria mensual:

| Código | Nombre | Cat. | afecto IGSS | afecto ISR | ordinario | Lógica (resumen) |
|---|---|---|---|---|---|---|
| `SALORD` | Salario ordinario | BASIC | ✔ | ✔ | ✔ | §4.1: sueldo pactado o proporcional a días trabajados (work entries) |
| `BONINC` | Bonificación Incentivo | ALW | ✘ | ✘ | ✘ | §4.2: monto vigente, proporcional a días; tope: ≤ salario ordinario |
| `HEXTD` | Horas extra diurnas | ALW | ✔ | ✔ | ✘ | §4.3: valor_hora × 1.5 × horas |
| `HEXTN` | Horas extra nocturnas | ALW | ✔ | ✔ | ✘ | §4.3: valor_hora × 2.0 × horas |
| `COMIS` | Comisiones | ALW | ✔ | ✔ | ✘ | §4.5: monto de novedad o fórmula |
| `BONIF` | Bonificaciones adicionales | ALW | config. | config. | config. | §4.4: flags por concepto |
| `IGSSLAB` | IGSS laboral | DED | — | (deducible ISR) | — | §4.9: base_igss × 4.83% |
| `ISR` | Retención ISR | DED | — | — | — | §4.10: cuota mensual de la proyección |
| `ANTIC` | Anticipos | DED | — | — | — | §4.11: saldo del período |
| `PREST` | Préstamos | DED | — | — | — | §4.12: cuota del plan |
| `OTRDED` | Otras deducciones | DED | — | — | — | §4.13: monto de novedad |
| `IGSSPAT` | IGSS patronal | COMP | — | — | — | §4.15: base_igss × 12.67% (no afecta líquido) |

**Base IGSS** (regla intermedia o `categories`): suma de líneas con `l10n_gt_afecto_igss = True`. En Odoo se resuelve con una categoría propia `GT_BASE_IGSS` y `categories.GT_BASE_IGSS` dentro del código Python de las reglas.

Ejemplo de código de la regla `IGSSLAB` (Python de `hr.salary.rule`):

```python
# base afecta = salario ordinario + horas extra + comisiones (marcadas afecto_igss)
base_igss = categories.GT_BASE_IGSS
tasa = payslip.rule_parameter('l10n_gt_igss_laboral')
result = -(base_igss * tasa)
```

Ejemplo `SALORD` con proporcionalidad por días (§4.1.2), leyendo work entries:

```python
# worked_days trae los días/horas del período desde hr.work.entry
dias_pagados = worked_days.WORK100.number_of_days if worked_days.WORK100 else 0
salario_mensual = contract.wage
if payslip._gt_periodo_completo():
    result = salario_mensual
else:
    salario_diario = salario_mensual / 30.0
    result = salario_diario * dias_pagados
```

### 3.4 Estructuras y tipos de nómina

- `structure.type`: **Nómina Mensual**, **Quincenal**, **Semanal** (§1.4.1), cada uno con su `resource.calendar` y periodicidad.
- `structure`: **Nómina Ordinaria GT** (reglas de §3.3), **Aguinaldo**, **Bono 14**, **Liquidación**. Las tres últimas son estructuras "especiales" que se corren en lotes independientes (§4.7.4, §4.8.4 piden planilla independiente).

### 3.5 Novedades (§2.4)

- Horas extra, comisiones, bonificaciones, otras deducciones → `hr.payslip.input.type` + `hr.payslip.input` (importables por Excel, §3.3.2 "Importar novedades").
- Ausencias/incapacidades/vacaciones → `hr.leave` (módulo `hr_holidays`) que generan `hr.work.entry` y reducen días pagados automáticamente.
- Anticipos/préstamos → desde `l10n_gt_payroll_loans` (§4).

---

## 4. `l10n_gt_payroll_isr` — proyección ISR (§4.10)

Es el proceso más complejo y **no existe en Odoo**. Modelo dedicado, reproduce el anexo 8.5.

```
l10n.gt.isr.projection
    employee_id, year, company_id
    state (borrador/vigente)
    line_ids → l10n.gt.isr.projection.line   (una por mes: enero..diciembre)
    Campos calculados anuales:
      renta_bruta_proyectada
      rentas_exentas          (aguinaldo + bono14)
      deduccion_personal      (param 51,024)
      igss_anual
      deducciones_comprobables (donaciones, seguro de vida — capturadas por el usuario)
      renta_imponible
      isr_anual
      retencion_mensual = isr_anual / 12
```

**Algoritmo** (`_compute_isr`):

1. Proyectar ingresos afectos ISR de los 12 meses: meses ya pagados usan el real de las nóminas; meses futuros usan el salario vigente del contrato.
2. `renta_imponible = renta_bruta - rentas_exentas - deduccion_personal - igss_anual - deducciones_comprobables`.
3. Impuesto por tramos:
   ```python
   if base <= 300000:
       isr = base * 0.05
   else:
       isr = 15000 + (base - 300000) * 0.07
   ```
4. `retencion_mes = (isr_anual - isr_retenido_acumulado) / meses_restantes` (el anexo 8.5 recalcula el saldo mensual conforme entran ingresos variables).

**Recálculo (§4.10.4):** se dispara al confirmar una nómina, al cambiar salario (nueva `hr.version`), o al registrar una deducción comprobable. La regla `ISR` del payslip solo **lee** `retencion_mensual` de la proyección vigente del empleado; no calcula.

Deducciones comprobables → modelo `l10n.gt.isr.deduction` (empleado, año, tipo, monto, constancia adjunta).

---

## 5. `l10n_gt_payroll_prestaciones` — Aguinaldo, Bono 14, vacaciones

### 5.1 Aguinaldo (§4.7) y Bono 14 (§4.8)

Ambos = promedio del salario ordinario mensual del período legal, proporcional al tiempo laborado. Se diferencian solo en la ventana:

| Prestación | Ventana |
|---|---|
| Aguinaldo | 1-dic (año -1) → 30-nov (año actual) |
| Bono 14 | 1-jul (año -1) → 30-jun (año actual) |

Implementación: estructura salarial especial + un asistente `l10n.gt.prestacion.wizard` que crea un `hr.payslip.run` con los payslips de la prestación. El promedio se calcula leyendo el histórico de salario ordinario (`hr.version` + nóminas ya generadas) sobre la ventana. Proporcionalidad: `(dias_laborados_en_ventana / 365) × salario_promedio`.

Reportes: **Planilla de Aguinaldo** (§6.3) y **Planilla de Bono 14** (§6.4) — listado por empleado con fecha ingreso, tiempo laborado, salario promedio, monto generado/proporcional.

### 5.2 Vacaciones (§4.6, §6.13)

Se apoya en `hr_holidays` para el saldo de días. Añadimos control del **acumulado por año de servicio** (15 días hábiles/año en GT) y el cálculo de pago solo en liquidación (§4.6.4). Reporte de vacaciones = días acumulados/gozados/pendientes.

---

## 6. `l10n_gt_payroll_liquidacion` — liquidaciones (§5) e indemnización (§4.16)

Modelo propio con su propia máquina de estados (§7.9.2):

```
l10n.gt.settlement
    employee_id, contract/version, fecha_baja, ultimo_dia, motivo_finalizacion,
    fecha_pago, observaciones
    state: borrador → calculada → aprobada → pagada / anulada
    line_ids: conceptos calculados
    genera: finiquito (PDF), boleta, asiento contable, cambio de empleado a inactivo
```

**Motivo de finalización** (Selection) determina automáticamente qué conceptos aplican (§5.6): p.ej. *despido* incluye indemnización; *renuncia* no.

**Conceptos** (§5.3): salario pendiente, bonif. incentivo pendiente, aguinaldo proporcional, bono 14 proporcional, vacaciones pendientes, indemnización, anticipos/préstamos pendientes, ISR/IGSS aplicables, devolución de ISR.

**Indemnización (§4.16)** — método `_compute_indemnizacion`:

```python
promedio_ord = promedio_salario_ordinario(ultimos_6_meses)   # o periodo trabajado si < 6m
salario_indemnizable = promedio_ord + aguinaldo/12 + bono14/12
años = (fecha_baja - fecha_ingreso).days / 365.0
indemnizacion = salario_indemnizable * años   # proporcional a fracciones
```

Validaciones (§5.6): no permitir dos liquidaciones para el mismo empleado + fecha de baja; al confirmar → empleado a **Inactivo** conservando historial. El cálculo debe reproducir el anexo 8.6 (caso Cristofer del Águila: 61 días, indemnización Q1,637.81, total Q5,687.40) como **prueba dorada**.

---

## 7. `l10n_gt_payroll_loans` — préstamos y anticipos (§4.11–12)

```
l10n.gt.loan
    employee_id, tipo (prestamo/anticipo), monto_original, fecha_otorgamiento,
    plan_ids → l10n.gt.loan.line  (cuota, fecha, estado pagada/pendiente)
    saldo_pendiente (computed), state (activo/cancelado/suspendido)
```

En el cálculo de nómina, las reglas `ANTIC`/`PREST` toman la cuota vigente del período y, al confirmar la nómina, marcan la cuota como pagada y actualizan el saldo (§4.12.4). Constraint: no descontar más que el saldo (§4.11.4). Reporte §6.12.

---

## 8. Reportes (capítulo 6)

Todos como QWeb (PDF) + exportación XLSX (`report_xlsx` de OCA o el motor XLSX de Enterprise). Características comunes §6.16: filtros por empresa/período/empleado/departamento, fecha-hora de generación, usuario, carta/oficio, datos históricos inmutables.

| Reporte | Fuente | Formato |
|---|---|---|
| Boleta de pago (§6.1) | `hr.payslip` | QWeb PDF (ver anexo 8.2) |
| Planilla general (§6.2) | `hr.payslip.run` | XLSX con totales por concepto (anexo 8.1) |
| Planilla Aguinaldo / Bono 14 (§6.3/4) | prestaciones | XLSX |
| Liquidación / finiquito (§6.5) | `l10n.gt.settlement` | QWeb PDF (anexo 8.6) |
| Reporte IGSS (§6.6) | payslips del mes | XLSX (base, cuota laboral, patronal) |
| Reporte ISR (§6.7) | `l10n.gt.isr.projection` | XLSX |
| Costos de personal (§6.8) | payslips + patronal | XLSX |
| Póliza contable (§6.9) | `account.move` o cálculo propio | PDF/XLSX independiente |
| Histórico nóminas/contratos (§6.10/11) | vistas lista | export estándar |
| **Libro de Salarios (§6.14)** | payslips históricos | XLSX con formato Acuerdo Ministerial 124-2019 (anexo 8.3) |
| **Informe del Empleador (§6.15)** | empleados + nóminas anuales | XLSX con códigos MinTrab (anexo 8.4) |

Los dos últimos son los de mayor esfuerzo por el formato legal exacto y los catálogos de códigos del Ministerio de Trabajo.

---

## 9. Contabilización (§2.9) y póliza (§6.9)

- Cada `hr.salary.rule` mapea débito/crédito a cuentas (`account.account`) configurables (§7.3).
- Al confirmar el lote → `account.move` vinculado (`hr.payslip.move_id`).
- Póliza independiente: `l10n_gt_payroll_account` genera el reporte de asiento **sin** postear en Contabilidad, para clientes que llevan su contabilidad fuera de Odoo (§6.9 lo pide explícitamente).

---

## 10. Estados, seguridad y auditoría

### 10.1 Estados (§7.9)

- **Período/lote** (`hr.payslip.run` extendido): Borrador → En cálculo → Calculado → Confirmado → Contabilizado → Cerrado. Mapear a los estados nativos y añadir "Cerrado" que bloquea recálculo (§7.8).
- **Liquidación**: Borrador → Calculada → Aprobada → Pagada / Anulada.

### 10.2 Seguridad (§7.4)

Grupos: `group_payroll_user` (consulta/captura), `group_payroll_manager` (aprobar, reabrir, liquidar, configurar). Reglas de registro por empresa (`multi-company`). Permisos por acción según la lista de §7.4.

### 10.3 Auditoría (§7.5)

`mail.thread` + `mail.tracking.value` sobre empleado, contrato, nómina, liquidación (usuario, fecha/hora, valores anterior/nuevo). Las nóminas confirmadas **congelan** sus líneas (§7.2): las `hr.payslip.line` no se recalculan aunque cambien parámetros después.

---

## 11. Validaciones clave (§7.1)

- No generar nómina sin período activo.
- No dos nóminas por empleado+período (constraint único).
- No incluir empleados inactivos salvo en liquidación.
- No modificar nómina confirmada salvo `group_payroll_manager`.
- No cerrar período con nóminas pendientes.
- Validar completitud de datos obligatorios del empleado antes de incluirlo.
- No períodos traslapados por tipo de nómina (§3.2.3).

---

## 12. Casos de prueba dorados (de los anexos)

Los anexos traen números reales → tests automatizados (`TransactionCase`):

1. **Anexo 8.1 (nómina interna URBOP jun-2026):** validar totales — Total sueldos Q223,236.08, ISR Q7,144.14, IGSS Q10,119.59, líquido Q205,972.35.
2. **Anexo 8.2 (recibo Glenda Pérez):** ordinario 4,002.28 + bonif 250 = 4,252.28; IGSS 193.31; ISR 2.95; líquido 4,056.02.
3. **Anexo 8.5 (proyección ISR Heidi Ávila):** enero renta imponible 23,502.90 → ISR anual 1,175.15 → retención mensual escalonada.
4. **Anexo 8.6 (liquidación Cristofer del Águila):** 61 días, Bono 14 1,403.84, aguinaldo 1,403.84, vacaciones 692.30, indemnización 1,637.81, total Q5,687.40.

Estos fijan la corrección de IGSS, ISR, prestaciones e indemnización.

---

## 13. Fases de entrega

| Fase | Módulos | Entregable verificable |
|---|---|---|
| **0** | `l10n_gt_hr` | Ficha de empleado/contrato GT + salario mínimo validado |
| **1** | `l10n_gt_payroll` + `l10n_gt_payroll_loans` | Nómina mensual con IGSS, bonif. incentivo, HE, préstamos + boleta (anexo 8.2) |
| **2** | `l10n_gt_payroll_isr` | Proyección + retención ISR (anexo 8.5) |
| **3** | `l10n_gt_payroll_prestaciones` | Aguinaldo, Bono 14, vacaciones + planillas |
| **4** | `l10n_gt_payroll_liquidacion` | Liquidación + indemnización (anexo 8.6) |
| **5** | `l10n_gt_payroll_account` + `l10n_gt_payroll_report` | Póliza, Libro de Salarios, Informe del Empleador |
| **6** | — | Permisos, auditoría, rendimiento masivo, multi-empresa |

Cada fase deja una nómina funcional y se valida contra los anexos antes de avanzar.

---

## 14. Riesgos y decisiones abiertas

1. **Formato exacto del Informe del Empleador y Libro de Salarios** — hay que conseguir las plantillas/nomenclatura oficiales vigentes del MinTrab (los anexos dan la estructura, pero los catálogos de códigos deben confirmarse).
2. **Devolución de ISR / RetenISR SAT (§5.3)** — la "cuadratura con el sistema RetenISR" puede requerir exportación en formato SAT; confirmar si es solo cálculo o también archivo de importación.
3. **Redondeos** — definir política (Odoo redondea por regla). Los anexos usan 2 decimales; hay pequeñas diferencias de centavos que hay que reproducir.
4. **Quincenal con anticipo de 1ª quincena** — el anexo 8.1 paga en dos quincenas (1ª y 2ª). Decidir si la 1ª quincena es un anticipo (sin deducciones) y la 2ª liquida IGSS/ISR del mes, o dos nóminas plenas. Esto afecta el diseño de la periodicidad.
5. **Odoo 18 `hr.version`** — validar en la instancia destino que el versionado de contratos expone las fechas necesarias para los cálculos históricos.

---

## 15. Próximo paso propuesto

Arrancar **Fase 0 + 1**: scaffold de `l10n_gt_hr` y `l10n_gt_payroll` (manifests, modelos, reglas salariales, parámetros legales, vista de boleta) y montar el primer test dorado con el anexo 8.2. Requiere acceso a una instancia Odoo 18 Enterprise para pruebas.

---

## 16. Segunda revisión — hallazgos y ajustes

Revisión crítica del documento funcional contra este plan y el scaffold, con verificación numérica contra los anexos. Los hallazgos se clasifican por prioridad.

### 16.1 Correcciones confirmadas con los anexos

| # | Hallazgo | Resolución |
|---|---|---|
| ✔ | **Deducción personal ISR**: §4.10 dice Q51,024, pero el anexo 8.5 y la ley vigente (Decreto 10-2012) usan **Q48,000**. Verificado: renta imponible 23,502.90 e ISR 1,175.15 solo cuadran con 48,000. | Parámetro `l10n_gt_isr_deduccion_personal = 48000`. El texto §4.10 se trata como **errata**. Confirmar con el cliente. |
| ✔ | **Sueldo diario promedio** para prestaciones = **salario mensual × 12 / 365** (Q276.16 en el anexo 8.6). Vacaciones = días devengados fraccionados (días/365 × 15) × diario promedio → Q692.30. El "3 días" mostrado es display redondeado. | Documentar como base diaria oficial GT para **vacaciones e indemnización**. Fijar en Fase 4 contra el anexo 8.6. |
| ✔ | Fase 1 verificada: IGSS lab 193.31, IGSS pat 507.09, neto 4,058.97; indemnización 1,637.81; aguinaldo/bono14 prop. 1,403.84. | Sin cambios. |

### 16.2 Prioridad ALTA — requieren decisión antes de avanzar

- **H1. Cambio salarial intra-período por tramos (§4.1.4).** La regla `SALORD` actual usa `contract.wage` plano; el documento exige prorratear por tramos cuando hay un cambio de salario dentro del período, leyendo el historial de contratos. **Enfoque a implementar**: en `_l10n_gt_worked_days`/`SALORD`, iterar las versiones de contrato que solapan `[date_from, date_to]` y sumar `salario_diario_tramo × días_tramo`. No se implementó en Fase 1 por depender del API de versionado de contratos de Odoo 18 (validar en instancia). **Debe cerrarse para dar Fase 1 por completa.**

- **H2. La "quincena" es un pago mensual dividido, no una nómina quincenal.** Evidencia anexo 8.1: las columnas "1ERA/2DA QUINCENA" son mitades iguales del líquido; IGSS/ISR se aplican **una vez al mes**, no por quincena. → El tipo de estructura primario debe ser **mensual con disbursement en 2 pagos**, no un `structure_type` quincenal que recalcule deducciones dos veces. Reajustar `hr_payroll_structure_type_data.xml` según la decisión del cliente (pregunta abierta #4).

- **H3. Automatización al confirmar la nómina (§2.8).** Al confirmar, el sistema debe disparar: recálculo de proyección ISR, borrador de planilla IGSS del mes, y generación de documentos. No hay hook aún. **Añadir** override de `action_payslip_done`/confirmación del lote en Fase 2 que encadene estos procesos.

### 16.3 Prioridad MEDIA — ajustes aplicados o programados

- **M1. Categoría IGSS (aplicado).** `GTIGSS` se definió como **hija de `BASIC`** para que `categories.BASIC` (usada por `basic_wage` y vistas de hr_payroll Enterprise) no quede vacía. `GROSS`/`NET` ahora usan `categories.BASIC + categories.ALW`; la base IGSS sigue siendo `categories.GTIGSS`.
- **M2. Desglose patronal (aplicado).** Se agregaron parámetros `l10n_gt_igss_patronal_igss` (10.67%), `l10n_gt_irtra` (1%), `l10n_gt_intecap` (1%) para el reporte de costos de personal (§6.8).
- **M3. Proporcionalidad de Bonif. Incentivo (§4.2.2).** El documento la condiciona a "legislación o políticas de la empresa". Debe hacerse **configurable** (parámetro `l10n_gt_boninc_prorratea`, default según política); actualmente la regla siempre prorratea.
- **M4. Estados del período.** Reconciliar §3.2.1 (Borrador/En Proceso/Confirmado/Cerrado) con §7.9.1 (añade En cálculo/Calculado/Contabilizado). Se adopta el **superconjunto de §7.9.1** como flujo oficial.
- **M5. Integración Asistencias (§7.6).** Añadir dependencia opcional de `hr_attendance`/`hr_work_entry` para importar horas extra y días desde marcajes cuando exista.

### 16.4 Prioridad BAJA — detalles para las fases de reportes/liquidación

- **L1.** Excluir horas extra también por **puesto** (`hr.job`), no solo por contrato (§4.3.4).
- **L2. Informe del Empleador (§6.15):** faltan mapeos a códigos MinTrab de género/estado civil/nacionalidad, expediente de permiso de trabajo (extranjeros), y fechas de inicio/reinicio/finalización separadas. Programado en Fase 5.
- **L3. Libro de Salarios (§6.14, anexo 8.3):** la columna "Ordinario" **excluye** la Bonificación Incentivo (que va en su propia columna Decreto 37-2001), y hay columna "Séptimos y asuetos". El modelo lo soporta (SALORD y BONINC separados); es layout del reporte. Ojo: el "Salario en Quetzales" del libro = SALORD + BONINC.
- **L4. Convención salario base ± bonificación.** Los anexos muestran **ambas convenciones** (URBOP: base excluye bonif; Range of Motion: base incluye bonif). El modelo es correcto si se captura `wage` = salario ordinario y `l10n_gt_bonif_incentivo` por separado; documentar esta regla de captura para evitar errores de migración de datos.

### 16.5 Veredicto de la revisión

El plan es **sólido y completo** en cobertura (los 15 reportes, capítulo 4 de cálculos, liquidaciones y estados están mapeados). Los cálculos de Fase 1, indemnización, aguinaldo/bono 14 e ISR están **verificados numéricamente** contra los anexos. Los tres puntos de prioridad alta (H1 tramos, H2 quincena, H3 automatización al confirmar) son **decisiones/implementaciones pendientes**, no errores de diseño, y ninguno invalida la arquitectura elegida (localización sobre `hr_payroll` Enterprise). Ajustes M1 y M2 ya aplicados al scaffold.
