# -*- coding: utf-8 -*-
"""Puesta a punto de la estructura salarial GT.

Al crear una estructura, Odoo 18 le agrega automáticamente un juego de reglas
estándar (Basic Salary, Taxable Salary, Net Salary, Child Support, etc.). La
nómina guatemalteca define su propio conjunto completo, así que esas reglas
estándar sobran (ensucian la boleta y duplican códigos GROSS/NET). Este hook
deja en la estructura únicamente las reglas propias del módulo.

Además completa la configuración que el usuario tendría que hacer a mano tras
instalar: los tipos de "Otras entradas" habilitados en la estructura y, si está
instalado hr_payroll_account (Enterprise), el Diario de salarios.
"""

# XMLIDs de las reglas que SÍ pertenecen a la nómina GT (incluye las de los
# submódulos ISR, préstamos y prestaciones; si no están instalados, se ignoran).
GT_RULE_XMLIDS = [
    "l10n_gt_payroll.rule_salord",
    "l10n_gt_payroll.rule_boninc",
    "l10n_gt_payroll.rule_hextd",
    "l10n_gt_payroll.rule_hextn",
    "l10n_gt_payroll.rule_comis",
    "l10n_gt_payroll.rule_bonif",
    "l10n_gt_payroll.rule_gross",
    "l10n_gt_payroll.rule_igsslab",
    "l10n_gt_payroll.rule_otrded",
    "l10n_gt_payroll.rule_net",
    "l10n_gt_payroll.rule_igsspat",
    "l10n_gt_payroll_isr.rule_isr",
    "l10n_gt_payroll_loans.rule_antic",
    "l10n_gt_payroll_loans.rule_prest",
    "l10n_gt_payroll_prestaciones.rule_vac",
    "l10n_gt_payroll_prestaciones.rule_prov_aguinaldo",
    "l10n_gt_payroll_prestaciones.rule_prov_bono14",
    "l10n_gt_payroll_prestaciones.rule_prov_indemnizacion",
]

# Tipos de nómina GT: todos usan la estructura ordinaria GT.
GT_STRUCTURE_TYPE_XMLIDS = [
    "l10n_gt_payroll.structure_type_gt_mensual",
    "l10n_gt_payroll.structure_type_gt_quincenal",
]

# Tipos de "Otras entradas" (novedades) que el recibo ordinario debe ofrecer.
GT_INPUT_TYPE_XMLIDS = [
    "l10n_gt_payroll.input_he_diurna",
    "l10n_gt_payroll.input_he_nocturna",
    "l10n_gt_payroll.input_comisiones",
    "l10n_gt_payroll.input_bonif_adicional",
    "l10n_gt_payroll.input_otras_deducciones",
]


def _gt_structure(env):
    return env.ref(
        "l10n_gt_payroll.structure_gt_ordinaria", raise_if_not_found=False)


def clean_structure_rules(env):
    structure = _gt_structure(env)
    if not structure:
        return
    keep = env["hr.salary.rule"].browse()
    for xmlid in GT_RULE_XMLIDS:
        rule = env.ref(xmlid, raise_if_not_found=False)
        if rule:
            keep |= rule
    strays = structure.rule_ids - keep
    if not strays:
        return
    # En instalación nueva se pueden borrar; si ya fueron usadas en recibos
    # (referencia en hr_payslip_line) no se pueden borrar y se archivan, para
    # que dejen de aparecer/calcularse sin romper el historial.
    try:
        with env.cr.savepoint():
            strays.unlink()
    except Exception:
        strays.write({"active": False})


def setup_structure_inputs(env):
    """Habilita en la estructura los tipos de "Otras entradas" GT que falten.

    Odoo 18 filtra el campo Tipo de las entradas del recibo por
    struct_id.input_line_type_ids; si la estructura no los tiene, la lista sale
    vacía. Solo agrega, nunca quita lo que el usuario haya habilitado a mano.
    """
    structure = _gt_structure(env)
    if not structure or "input_line_type_ids" not in structure._fields:
        return
    missing = env["hr.payslip.input.type"].browse()
    for xmlid in GT_INPUT_TYPE_XMLIDS:
        it = env.ref(xmlid, raise_if_not_found=False)
        if it and it not in structure.input_line_type_ids:
            missing |= it
    if missing:
        structure.write({"input_line_type_ids": [(4, it.id) for it in missing]})


def setup_structure_journal(env):
    """Asigna el Diario de salarios de la estructura si está vacío.

    El campo lo agrega hr_payroll_account (Enterprise), que no es dependencia de
    este módulo; por eso se comprueba en tiempo de ejecución. Sin diario, Odoo no
    deja guardar el recibo ("Campos no válidos: Diario de salarios"). Se usa un
    diario tipo 'general' de la empresa (preferido el código SLR); no se crea
    ninguno, para no inventar contabilidad.
    """
    structure = _gt_structure(env)
    if not structure or "journal_id" not in structure._fields:
        return
    if "account.journal" not in env:
        return
    Journal = env["account.journal"]
    for company in env["res.company"].search([]):
        struct = structure.with_company(company)
        if struct.journal_id:
            continue
        domain = [("type", "=", "general"), ("company_id", "=", company.id)]
        journal = (Journal.search(domain + [("code", "=", "SLR")], limit=1)
                   or Journal.search(domain, limit=1))
        if journal:
            struct.journal_id = journal


def setup_structure_type_default(env):
    """Hace de la estructura GT la estructura por defecto de su tipo de nómina.

    El asistente estándar "Generar recibos" del lote (y hr.payslip._compute_struct_id)
    toman la estructura de structure_type_id.default_struct_id; sin esto los
    recibos generados en lote salen SIN estructura (sin líneas) y el usuario
    termina creándolos uno por uno desde el formulario.
    """
    structure = _gt_structure(env)
    if not structure:
        return
    # Ambos tipos GT calculan por MES con la misma estructura (el pago quincenal
    # es la frecuencia del contrato, no otra estructura). Sin esto, los contratos
    # con tipo "Nómina Quincenal" generaban recibos en 0.
    for xmlid in GT_STRUCTURE_TYPE_XMLIDS:
        stype = env.ref(xmlid, raise_if_not_found=False)
        if stype and not stype.default_struct_id:
            stype.default_struct_id = structure


def gt_structure_types(env):
    types = env["hr.payroll.structure.type"]
    for xmlid in GT_STRUCTURE_TYPE_XMLIDS:
        types |= env.ref(xmlid, raise_if_not_found=False) or types.browse()
    return types


def fix_slips_without_structure(env):
    """Recibos en borrador / en espera SIN estructura cuyo contrato es de un tipo
    GT: se les asigna la estructura GT (salían en 0). No los recalcula: las reglas
    usan campos de submódulos (p. ej. VAC de prestaciones) que aún no están
    cargados mientras se actualiza este módulo; ver recompute_empty_slips."""
    structure = _gt_structure(env)
    if not structure:
        return
    slips = env["hr.payslip"].search([
        ("struct_id", "=", False),
        ("state", "in", ("draft", "verify")),
        ("contract_id.structure_type_id", "in", gt_structure_types(env).ids),
    ])
    if slips:
        slips.write({"struct_id": structure.id})


def recompute_empty_slips(env):
    """Recalcula los recibos GT abiertos que no tienen líneas (con todos los
    módulos ya cargados: se llama desde un end-migrate)."""
    structure = _gt_structure(env)
    if not structure:
        return
    slips = env["hr.payslip"].search([
        ("struct_id", "=", structure.id),
        ("state", "in", ("draft", "verify")),
        ("line_ids", "=", False),
    ])
    if slips:
        slips.compute_sheet()


def setup_structure(env):
    clean_structure_rules(env)
    setup_structure_inputs(env)
    setup_structure_journal(env)
    setup_structure_type_default(env)


def post_init_hook(env):
    setup_structure(env)
