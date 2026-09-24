# Módulo de Nómina Guatemala — Odoo 18 Enterprise

Localización de nómina guatemalteca sobre `hr_payroll` (Enterprise), según el
*Diseño Funcional de Módulo de Nómina v1.0*. Ver [docs/plan-tecnico-nomina-gt.md](docs/plan-tecnico-nomina-gt.md).

## Módulos y orden de instalación

Instalar en este orden (cada uno declara sus dependencias, Odoo resuelve el orden):

| # | Módulo | Depende de | Cubre |
|---|---|---|---|
| 1 | `l10n_gt_hr` | hr, hr_contract | Empleado/contrato GT, DPI/NIT/IGSS, circunscripción y salario mínimo |
| 2 | `l10n_gt_payroll` | l10n_gt_hr, **hr_payroll**, hr_work_entry_contract | Reglas, estructuras, parámetros legales, período con estados, salario ordinario por tramos, IGSS |
| 3 | `l10n_gt_payroll_isr` | l10n_gt_payroll | Proyección anual ISR + retención mensual (§4.10) |
| 4 | `l10n_gt_payroll_loans` | l10n_gt_payroll | Préstamos y anticipos (§4.11, §4.12) |
| 5 | `l10n_gt_payroll_prestaciones` | l10n_gt_payroll | Aguinaldo, Bono 14, vacaciones (§4.6–4.8) |
| 6 | `l10n_gt_payroll_liquidacion` | l10n_gt_payroll_prestaciones | Liquidación, indemnización, finiquito (§4.16, §5) |
| 7 | `l10n_gt_payroll_account` | l10n_gt_payroll, account | Cuentas por concepto y póliza (§2.9, §6.9) |
| 8 | `l10n_gt_payroll_report` | l10n_gt_payroll | Boleta, planilla, IGSS, costos, Libro de Salarios, Informe del Empleador (§6) |
| 9 | `l10n_gt_payroll_report_xlsx` | l10n_gt_payroll_report, **report_xlsx** (OCA) | Nómina de sueldos y salarios en Excel con el formato del cliente (§6.2) |

> **Requiere Odoo 18 Enterprise** (el motor `hr_payroll` es Enterprise).

## Instalación

```bash
# Copiar las 8 carpetas l10n_gt_* al addons_path y:
odoo -d MI_BD -i l10n_gt_payroll_isr,l10n_gt_payroll_loans,\
l10n_gt_payroll_prestaciones,l10n_gt_payroll_liquidacion,\
l10n_gt_payroll_account,l10n_gt_payroll_report --stop-after-init
```

## Pruebas (casos dorados de los anexos)

```bash
odoo -d MI_BD --test-enable --test-tags l10n_gt --stop-after-init
```

- `l10n_gt_payroll`: nómina de Glenda (anexo 8.1/8.2) → IGSS 193.31, líquido 4,058.97.
- `l10n_gt_payroll_liquidacion`: liquidación de Cristofer (anexo 8.6) → aguinaldo/bono14 1,403.84, indemnización 1,637.81, vacaciones 692.30.

## Referencias externas a verificar en la primera instalación

El desarrollo se hizo sin una instancia Enterprise a mano. Estos IDs externos son
estándar pero **conviene confirmarlos** contra la versión exacta de `hr_payroll` 18
Enterprise instalada (si algún ID cambió, ajustar el `inherit_id`/`ref`):

- `hr_payroll.menu_hr_payroll_root` (raíz de menús)
- `hr_payroll.hr_payslip_run_form`, `hr_payroll.hr_salary_rule_form` (vistas heredadas)
- `hr_contract.hr_contract_view_form` (vista de contrato heredada)
- Categorías `hr_payroll.BASIC/ALW/DED/GROSS/NET`
- Método `hr.payslip.action_payslip_done` (override en ISR y préstamos)

## Parámetros legales (configurables sin código, §7.3)

Todos versionados por fecha en *Configuración → Parámetros de reglas salariales*:
IGSS laboral 4.83%, patronal 12.67% (IGSS 10.67 + IRTRA 1 + INTECAP 1), Bonif.
Incentivo mínima Q250, ISR deducción personal **Q48,000** (ver nota), tramos ISR
5% / 7% + Q15,000, factores de hora extra 1.5 / 2.0, salario mínimo por circunscripción.

## Notas y simplificaciones conocidas

1. **ISR deducción personal Q48,000**: el texto §4.10 dice Q51,024, pero el anexo
   8.5 y la ley vigente usan Q48,000 (parámetro configurable).
2. **Quincena**: la estructura primaria es **mensual** (el anexo 8.1 aplica IGSS/ISR
   una vez al mes y divide el pago en dos). El tipo quincenal existe pero no recalcula
   deducciones por quincena.
3. **Libro de Salarios e Informe del Empleador**: reportes QWeb funcionales con las
   columnas documentadas. El layout legal exacto y los códigos de nomenclatura MinTrab
   deben afinarse contra la plantilla oficial vigente (idealmente export XLSX vía
   `report_xlsx`).
4. **Devolución ISR / RetenISR SAT** (§5.3): pendiente de definir el formato de
   exportación SAT.
5. **Vacaciones**: los **días gozados** (descanso pagado, no cambian el salario) se
   anotan en el bloque *Vacaciones* de *Días trabajados y entradas*, junto al saldo.
   Los **días pagados** se capturan en la tabla de *Cálculo del salario* (línea
   *Vacaciones pagadas*, días en Cantidad) y generan `VAC` = días × sueldo diario
   promedio, que llega a planilla, Libro de Salarios, IGSS/ISR y póliza. Ambos bajan
   el mismo saldo. `VAC` está afecta a IGSS/ISR y en la base de provisiones
   (categoría GTIGSS); si el contador indica otro tratamiento, se ajusta en la regla.
   Las vacaciones pendientes de un **finiquito** siguen pagándose como línea del
   Estado de Cuenta (drenan el pasivo).
6. **Captura en una sola tabla**: en *Cálculo del salario* se captura todo. Horas
   extra y vacaciones pagadas: horas/días en **Cantidad**. Bonificaciones,
   comisiones y otras deducciones: monto en **Total** (se guarda como la entrada
   del recibo; la sección nativa *Otras entradas* queda oculta). Cualquier otro
   concepto (ISR, IGSS, salario…): editar su **Total** lo fija como **ajuste
   manual**, aplicado dentro del motor de reglas (el líquido, deducciones
   dependientes y póliza salen consistentes), marcado en amarillo, con historial y
   chatter; reescribir el valor calculado o borrarlo del historial lo deshace. Se
   agregan filas con *Agregar una línea* y se quitan con la papelera. Al guardar
   se recalcula la hoja. Subtotales (GROSS/NET) no editables; todo se bloquea al
   confirmar.
7. **Nómina de sueldos y salarios**: desde el lote, *Imprimir → Nómina de sueldos y
   salarios (Excel)* (módulo `l10n_gt_payroll_report_xlsx`) o *(PDF)*; mismas
   columnas que la hoja del cliente. Firmas en *Empresa → Nómina GT*. La columna
   "DPI" muestra el DPI completo del empleado. Lo que no tiene columna propia (comisiones, vacaciones pagadas) suma en
   *Sueldo Devengado*. Quincenas según el método del recibo; si el ingreso es
   después del 15, todo va a la segunda. El PDF requiere `wkhtmltopdf` en el
   servidor.
