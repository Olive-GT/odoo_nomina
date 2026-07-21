# -*- coding: utf-8 -*-
from odoo import fields, models


class HrSalaryRule(models.Model):
    """Marcas guatemaltecas para clasificar cada concepto (§4)."""

    _inherit = "hr.salary.rule"

    l10n_gt_afecto_igss = fields.Boolean(
        "Afecto a IGSS",
        help="El concepto forma parte de la base de cálculo del IGSS "
             "(salario ordinario, horas extra, comisiones). §4.9.",
    )
    l10n_gt_afecto_isr = fields.Boolean(
        "Afecto a ISR",
        help="El concepto entra en la proyección de ISR asalariados. §4.10.",
    )
    l10n_gt_es_ordinario = fields.Boolean(
        "Forma parte del salario ordinario",
        help="Base para prestaciones (aguinaldo, bono 14, indemnización). §4.4.4.",
    )
