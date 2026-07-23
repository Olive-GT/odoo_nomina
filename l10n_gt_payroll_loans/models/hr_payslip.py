# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    # ------------------------------------------------------------------
    # Anticipos de sueldo (como líneas del Estado de Cuenta)
    # ------------------------------------------------------------------
    l10n_gt_advance_pending = fields.Monetary(
        "Saldo de anticipos", compute="_compute_l10n_gt_advance_pending",
        help="Anticipos entregados menos recuperados del empleado (según recibos "
             "confirmados). Se registra y recupera con líneas de tipo 'Anticipo "
             "entregado' y 'Recuperación de anticipo' en el Estado de Cuenta.")

    @api.depends("employee_id", "l10n_gt_payment_ids.amount",
                 "l10n_gt_payment_ids.benefit_type")
    def _compute_l10n_gt_advance_pending(self):
        for slip in self:
            slip.l10n_gt_advance_pending = slip._l10n_gt_advance_balance()

    def _l10n_gt_advance_balance(self):
        """Saldo de anticipos del empleado = entregados − recuperados, sobre
        recibos confirmados (no cuenta el recibo en borrador actual)."""
        self.ensure_one()
        if not self.employee_id:
            return 0.0
        Payment = self.env["l10n.gt.payslip.payment"]

        def _sum(btype):
            return sum(Payment.search([
                ("payslip_id.employee_id", "=", self.employee_id.id),
                ("payslip_id.state", "in", ("done", "paid")),
                ("benefit_type", "=", btype),
            ]).mapped("amount"))

        return _sum("anticipo_given") - _sum("anticipo_recover")

    def _l10n_gt_advance_recover_amount(self):
        """Recuperación de anticipos capturada en ESTE recibo (líneas
        'anticipo_recover'), sin exceder el saldo disponible. Alimenta la
        deducción ANTIC del cálculo del salario."""
        self.ensure_one()
        requested = sum(self.l10n_gt_payment_ids.filtered(
            lambda p: p.benefit_type == "anticipo_recover").mapped("amount"))
        return min(requested, max(self._l10n_gt_advance_balance(), 0.0))

    # ------------------------------------------------------------------
    # Préstamos / anticipos formales con cuotas
    # ------------------------------------------------------------------
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
        total = 0.0
        for loan in lines.mapped("loan_id"):
            due = sum(lines.filtered(lambda l: l.loan_id == loan).mapped("amount"))
            total += min(due, loan.balance)
        return total

    def action_payslip_done(self):
        """Al confirmar, marcar como pagadas las cuotas descontadas (§4.12.4)."""
        res = super().action_payslip_done()
        for slip in self:
            for loan_type in ("loan", "advance"):
                lines = slip._l10n_gt_loan_lines_due(loan_type)
                lines.sudo().write({
                    "state": "paid",
                    "payslip_id": slip.id,
                    "paid_date": slip.date_to,
                })
        return res
