# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_gt_payslip_period = fields.Selection(
        selection=[("monthly", "Mensual"), ("biweekly", "Quincenal")],
        string="Modalidad de comprobante de nómina",
        default="monthly",
        help="Define qué comprobante se entrega al trabajador. El cálculo de la "
             "nómina siempre es mensual; esta opción solo indica si se imprime una "
             "boleta mensual o dos comprobantes quincenales.",
    )
