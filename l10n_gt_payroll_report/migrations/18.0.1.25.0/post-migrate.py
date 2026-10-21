# -*- coding: utf-8 -*-
"""El @api.depends del estado de cuenta estaba sobre otro método, así que
líquido/pagado/pendiente/estado de pago nunca se recalcularon (quedaron NULL y
"Sin pagar" en todos los recibos). Se recalculan para los recibos existentes."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    slips = env["hr.payslip"].search([])
    slips._compute_l10n_gt_estado_cuenta()
    env.flush_all()
