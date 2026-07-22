# -*- coding: utf-8 -*-
"""El tipo de nómina 'Quincenal' pasa a calcular por mes (IGSS/ISR son mensuales).
El pago quincenal se maneja al imprimir los comprobantes, no en el período de
cálculo. Esto evita que los recibos se autocompleten a 14 días."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    st = env.ref("l10n_gt_payroll.structure_type_gt_quincenal",
                 raise_if_not_found=False)
    if st and st.default_schedule_pay != "monthly":
        st.default_schedule_pay = "monthly"
