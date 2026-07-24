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
