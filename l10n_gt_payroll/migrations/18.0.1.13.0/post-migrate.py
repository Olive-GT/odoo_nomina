# -*- coding: utf-8 -*-
"""La estructura GT se creó sin tipos de "Otras entradas" habilitados (en Odoo 18
el recibo solo ofrece los de struct_id.input_line_type_ids, así que la lista salía
vacía) y, con hr_payroll_account instalado, sin Diario de salarios (bloqueaba el
guardado del recibo). El XML de la estructura es noupdate, por eso se completa aquí
para las bases ya instaladas."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.l10n_gt_payroll.hooks import (
        setup_structure_inputs, setup_structure_journal)
    setup_structure_inputs(env)
    setup_structure_journal(env)
