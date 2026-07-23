# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    # ------------------------------------------------------------------
    # Anticipos de sueldo (flexibles): saldo pendiente + recuperación
    # ------------------------------------------------------------------
    l10n_gt_advance_pending = fields.Monetary(
        "Anticipos pendientes", compute="_compute_l10n_gt_advance_pending",
        help="Saldo de anticipos de sueldo que el empleado aún no ha devuelto.")
    l10n_gt_advance_recover = fields.Monetary(
        "Descontar de anticipos",
        help="Cuánto recuperar de los anticipos pendientes en ESTE recibo (total o "
             "parcial, cuando la empresa lo decida). Se descuenta del líquido y baja "
             "el saldo del anticipo. Déjalo en 0 para no recuperar este mes.")
    l10n_gt_advance_ids = fields.One2many(
        related="employee_id.l10n_gt_advance_ids",
        string="Anticipos del empleado", readonly=True)

    def action_l10n_gt_new_advance(self):
        """Registrar un anticipo del empleado directo desde el recibo."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Registrar anticipo",
            "res_model": "l10n.gt.advance",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_employee_id": self.employee_id.id,
                "default_date": self.date_from,
            },
        }

    @api.depends("employee_id")
    def _compute_l10n_gt_advance_pending(self):
        for slip in self:
            advances = self.env["l10n.gt.advance"].search([
                ("employee_id", "=", slip.employee_id.id),
                ("state", "=", "pending"),
            ])
            slip.l10n_gt_advance_pending = sum(advances.mapped("balance"))

    def _l10n_gt_advance_recover_amount(self):
        """Monto real a recuperar este período: lo solicitado, sin exceder el saldo
        pendiente de anticipos del empleado."""
        self.ensure_one()
        return min(self.l10n_gt_advance_recover or 0.0, self.l10n_gt_advance_pending)

    def _l10n_gt_apply_advance_recovery(self):
        """Aplica la recuperación de anticipos al confirmar: crea las devoluciones
        (FIFO por fecha) y baja el saldo. Evita doble aplicación si el recibo ya
        tenía devoluciones registradas."""
        self.ensure_one()
        if self.env["l10n.gt.advance.recovery"].search_count([
                ("payslip_id", "=", self.id)]):
            return
        remaining = self._l10n_gt_advance_recover_amount()
        if remaining <= 0:
            return
        advances = self.env["l10n.gt.advance"].search([
            ("employee_id", "=", self.employee_id.id),
            ("state", "=", "pending"),
        ], order="date, id")
        Recovery = self.env["l10n.gt.advance.recovery"].sudo()
        for adv in advances:
            if remaining <= 0.005:
                break
            take = min(remaining, adv.balance)
            if take <= 0:
                continue
            Recovery.create({
                "advance_id": adv.id,
                "payslip_id": self.id,
                "date": self.date_to,
                "amount": take,
            })
            remaining -= take

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
        # Cap al saldo pendiente por préstamo
        total = 0.0
        for loan in lines.mapped("loan_id"):
            due = sum(lines.filtered(lambda l: l.loan_id == loan).mapped("amount"))
            total += min(due, loan.balance)
        return total

    def action_payslip_done(self):
        """Al confirmar: marcar cuotas pagadas y aplicar la recuperación de
        anticipos flexibles (§4.11.4/§4.12.4)."""
        res = super().action_payslip_done()
        for slip in self:
            for loan_type in ("loan", "advance"):
                lines = slip._l10n_gt_loan_lines_due(loan_type)
                # Efecto de sistema al confirmar: marcar cuotas pagadas con sudo.
                lines.sudo().write({
                    "state": "paid",
                    "payslip_id": slip.id,
                    "paid_date": slip.date_to,
                })
            slip._l10n_gt_apply_advance_recovery()
        return res
