# -*- coding: utf-8 -*-
"""Recalcula los recibos que post-migrate dejó con estructura pero sin líneas.
Va en 'end' porque las reglas dependen de submódulos (prestaciones, ISR) que se
cargan después de l10n_gt_payroll."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.l10n_gt_payroll.hooks import recompute_empty_slips
    recompute_empty_slips(env)
