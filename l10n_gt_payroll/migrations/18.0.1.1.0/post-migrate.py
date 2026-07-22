# -*- coding: utf-8 -*-
"""Quita de la estructura GT las reglas estándar de Odoo que se colaron
al crear la estructura (Basic Salary, Taxable Salary, Net Salary, etc.)."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.l10n_gt_payroll.hooks import clean_structure_rules
    clean_structure_rules(env)
