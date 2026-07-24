# -*- coding: utf-8 -*-
from odoo import models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _l10n_gt_advance_summary(self):
        """Resumen de anticipos del empleado (§6.12): entregado, recuperado y
        saldo pendiente, sobre recibos confirmados/pagados."""
        self.ensure_one()
        Payment = self.env["l10n.gt.payslip.payment"]
        base = [("payslip_id.employee_id", "=", self.id), ("paid", "=", True)]
        given = sum(Payment.search(
            base + [("benefit_type", "=", "anticipo_given")]).mapped("amount"))
        recovered = sum(Payment.search(
            base + [("benefit_type", "=", "anticipo_recover")]).mapped("amount"))
        return {"given": given, "recovered": recovered,
                "balance": given - recovered}
