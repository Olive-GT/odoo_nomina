# -*- coding: utf-8 -*-
"""Nuevo concepto "Asueto trabajado": se habilita su tipo de entrada en la
estructura GT de las bases existentes (el XML de la estructura es noupdate)."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.l10n_gt_payroll.hooks import setup_structure_inputs
    setup_structure_inputs(env)
