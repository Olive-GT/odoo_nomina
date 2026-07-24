# -*- coding: utf-8 -*-
# Limpieza de reglas salariales huérfanas del diseño anterior de anticipos/
# préstamos. Los anticipos ahora son líneas del Estado de Cuenta; las reglas
# ANTIC/PREST (que invocaban el método ya eliminado _l10n_gt_loan_deduction)
# quedaron en la BD y rompen el cálculo de la nómina. Se eliminan aquí.
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    rules = env["hr.salary.rule"].search([]).filtered(
        lambda r: "_l10n_gt_loan_deduction" in (
            (r.condition_python or "") + (r.amount_python_compute or "")))
    if not rules:
        return
    # Borra primero las líneas de recibo que referencian estas reglas para que
    # el unlink no falle por integridad referencial.
    cr.execute(
        "DELETE FROM hr_payslip_line WHERE salary_rule_id IN %s",
        (tuple(rules.ids),),
    )
    rules.unlink()
