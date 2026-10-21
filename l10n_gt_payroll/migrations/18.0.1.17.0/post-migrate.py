# -*- coding: utf-8 -*-
"""El tipo de nómina GT no tenía estructura por defecto: "Generar recibos" del
lote creaba recibos sin estructura (sin líneas) y el cliente terminó creando los
recibos uno por uno. Se asigna la estructura GT como default_struct_id."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.l10n_gt_payroll.hooks import setup_structure_type_default
    setup_structure_type_default(env)
