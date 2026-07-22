# -*- coding: utf-8 -*-
"""Ordena la configuración de nómina GT:
- El tipo de estructura deja de nombrarse por frecuencia -> 'Nómina (Guatemala)'
  (solo indica QUÉ reglas calculan, no la frecuencia).
- 'Programar pago' (schedule_pay) de los contratos GT pasa a Mensual, para que el
  salario se interprete como mensual (evita el '/ medio mes').
La frecuencia de pago (comprobantes) queda en el campo propio del contrato
l10n_gt_payment_frequency."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    types = env["hr.payroll.structure.type"].browse()
    for xmlid in ("structure_type_gt_mensual", "structure_type_gt_quincenal"):
        st = env.ref("l10n_gt_payroll." + xmlid, raise_if_not_found=False)
        if st:
            st.name = "Nómina (Guatemala)"
            st.default_schedule_pay = "monthly"
            types |= st
    # Salario mensual en los contratos GT (evita el "/ medio mes").
    if types and "schedule_pay" in env["hr.contract"]._fields:
        contracts = env["hr.contract"].search([
            ("structure_type_id", "in", types.ids)])
        contracts.write({"schedule_pay": "monthly"})
