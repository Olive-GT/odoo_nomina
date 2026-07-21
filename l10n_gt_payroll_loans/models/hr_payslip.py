# -*- coding: utf-8 -*-
from odoo import models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def _l10n_gt_loan_lines_due(self, loan_type):
        """Cuotas pendientes exigibles en el período para un tipo (préstamo/anticipo)."""
        self.ensure_one()
        return self.env["l10n.gt.loan.line"].search([
            ("loan_id.employee_id", "=", self.employee_id.id),
            ("loan_id.loan_type", "=", loan_type),
            ("loan_id.state", "=", "active"),
            ("state", "=", "pending"),
            ("due_date", "<=", self.date_to),
        ])

    def _l10n_gt_loan_deduction(self, loan_type):
        """Monto a descontar en el período. No supera el saldo pendiente
        (§4.11.4)."""
        self.ensure_one()
        lines = self._l10n_gt_loan_lines_due(loan_type)
        # Cap al saldo pendiente por préstamo
        total = 0.0
        for loan in lines.mapped("loan_id"):
            due = sum(lines.filtered(lambda l: l.loan_id == loan).mapped("amount"))
            total += min(due, loan.balance)
        return total

    def action_payslip_done(self):
        """Al confirmar, marcar como pagadas las cuotas descontadas y actualizar
        el saldo (§4.12.4)."""
        res = super().action_payslip_done()
        for slip in self:
            for loan_type in ("loan", "advance"):
                lines = slip._l10n_gt_loan_lines_due(loan_type)
                lines.write({
                    "state": "paid",
                    "payslip_id": slip.id,
                    "paid_date": slip.date_to,
                })
        return res
