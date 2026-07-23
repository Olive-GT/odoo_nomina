# -*- coding: utf-8 -*-
"""Elimina el tipo de entrada 'Anticipo de sueldo' (input_anticipo) que se probó
brevemente: los anticipos ahora se manejan con el modelo flexible l10n.gt.advance,
no como una entrada directa del recibo."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    it = env.ref("l10n_gt_payroll.input_anticipo", raise_if_not_found=False)
    if it:
        try:
            with env.cr.savepoint():
                it.unlink()
        except Exception:
            pass
