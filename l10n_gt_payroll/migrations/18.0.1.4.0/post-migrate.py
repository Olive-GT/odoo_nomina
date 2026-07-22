# -*- coding: utf-8 -*-
"""Deja UN solo tipo de estructura GT ('Nómina (Guatemala)', mensual):
- Reasigna los contratos que usaban el tipo 'Quincenal' al tipo único.
- Archiva el tipo duplicado.
- Pone schedule_pay=monthly en los contratos GT (salario mensual, sin '/ medio mes').
Así la Estructura del recibo se hereda limpio y no hay dos tipos confusos."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    mensual = env.ref("l10n_gt_payroll.structure_type_gt_mensual",
                      raise_if_not_found=False)
    quincenal = env.ref("l10n_gt_payroll.structure_type_gt_quincenal",
                        raise_if_not_found=False)
    if not mensual:
        return
    mensual.name = "Nómina (Guatemala)"
    mensual.default_schedule_pay = "monthly"
    if quincenal and quincenal != mensual:
        env["hr.contract"].search([
            ("structure_type_id", "=", quincenal.id),
        ]).write({"structure_type_id": mensual.id})
        quincenal.active = False
    if "schedule_pay" in env["hr.contract"]._fields:
        env["hr.contract"].search([
            ("structure_type_id", "=", mensual.id),
        ]).write({"schedule_pay": "monthly"})
