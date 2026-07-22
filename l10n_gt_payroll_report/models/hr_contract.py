# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrContract(models.Model):
    _inherit = "hr.contract"

    l10n_gt_payment_frequency = fields.Selection(
        selection=[
            ("monthly", "Mensual"),
            ("biweekly", "Quincenal"),
            ("weekly", "Semanal"),
        ],
        string="Frecuencia de pago",
        default=lambda self: self.env.company.l10n_gt_payslip_period or "biweekly",
        help="Cómo se le paga a este empleado. El cálculo de la nómina SIEMPRE es "
             "mensual (por IGSS/ISR); esto solo define en cuántos comprobantes se "
             "reparte el pago del mes:\n"
             "- Mensual: 1 comprobante (el mes completo).\n"
             "- Quincenal: 2 comprobantes (1ª y 2ª quincena).\n"
             "- Semanal: 4 comprobantes (semana 1 a 4).",
    )
