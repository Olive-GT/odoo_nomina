# -*- coding: utf-8 -*-
"""El tipo "Nómina Quincenal (Guatemala)" no tenía estructura por defecto: los
contratos con ese tipo generaban en el lote recibos sin estructura (en 0). Se
asigna la estructura GT a ambos tipos y se corrigen y recalculan los recibos
abiertos que quedaron sin estructura."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.l10n_gt_payroll.hooks import (
        fix_slips_without_structure, setup_structure_type_default)
    setup_structure_type_default(env)
    fix_slips_without_structure(env)
