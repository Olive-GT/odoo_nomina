# -*- coding: utf-8 -*-
"""Limpieza de la estructura salarial GT.

Al crear una estructura, Odoo 18 le agrega automáticamente un juego de reglas
estándar (Basic Salary, Taxable Salary, Net Salary, Child Support, etc.). La
nómina guatemalteca define su propio conjunto completo, así que esas reglas
estándar sobran (ensucian la boleta y duplican códigos GROSS/NET). Este hook
deja en la estructura únicamente las reglas propias del módulo.
"""

# XMLIDs de las reglas que SÍ pertenecen a la nómina GT (incluye las de los
# submódulos ISR y préstamos; si no están instalados, se ignoran).
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
]


def clean_structure_rules(env):
    structure = env.ref(
        "l10n_gt_payroll.structure_gt_ordinaria", raise_if_not_found=False)
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


def post_init_hook(env):
    clean_structure_rules(env)
