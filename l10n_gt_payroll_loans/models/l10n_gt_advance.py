# -*- coding: utf-8 -*-
from odoo import api, models, fields


class L10nGtPayslipPayment(models.Model):
    """Anticipos estandarizados como líneas del Estado de Cuenta (igual que Bono 14
    / Aguinaldo): 'Anticipo entregado' registra el dinero dado y 'Recuperación de
    anticipo' lo descuenta. Cada uno tiene su propio comprobante."""

    _inherit = "l10n.gt.payslip.payment"

    benefit_type = fields.Selection(
        selection_add=[
            ("anticipo_given", "Anticipo entregado"),
            ("anticipo_recover", "Recuperación de anticipo"),
        ],
        ondelete={
            "anticipo_given": "set default",
            "anticipo_recover": "set default",
        },
    )

    @api.onchange("benefit_type")
    def _l10n_gt_onchange_advance_type(self):
        """Propone concepto y monto para las líneas de anticipo."""
        if self.benefit_type == "anticipo_given":
            if not self.name or self.name == "Pago":
                self.name = "Anticipo entregado"
        elif self.benefit_type == "anticipo_recover":
            if not self.name or self.name == "Pago":
                self.name = "Recuperación de anticipo"
            if not self.amount and self.payslip_id:
                self.amount = max(
                    self.payslip_id._l10n_gt_advance_balance(), 0.0)
