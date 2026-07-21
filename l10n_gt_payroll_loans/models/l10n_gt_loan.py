# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class L10nGtLoan(models.Model):
    """Préstamo o anticipo con plan de cuotas (§4.11, §4.12, §6.12)."""

    _name = "l10n.gt.loan"
    _description = "Préstamo / Anticipo de empleado"
    _order = "date_grant desc"

    name = fields.Char(default="Nuevo", copy=False)
    employee_id = fields.Many2one("hr.employee", required=True, ondelete="restrict")
    loan_type = fields.Selection(
        selection=[("loan", "Préstamo"), ("advance", "Anticipo")],
        string="Tipo", required=True, default="loan",
    )
    date_grant = fields.Date("Fecha de otorgamiento", required=True,
                             default=fields.Date.context_today)
    amount = fields.Monetary("Monto original", required=True)
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.ref("base.GTQ", raise_if_not_found=False),
    )
    installments = fields.Integer("Número de cuotas", default=1)
    line_ids = fields.One2many("l10n.gt.loan.line", "loan_id", string="Plan de pagos")
    amount_paid = fields.Monetary(compute="_compute_balance", store=True)
    balance = fields.Monetary("Saldo pendiente", compute="_compute_balance", store=True)
    state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("active", "Activo"),
            ("cancelled", "Cancelado"),
            ("suspended", "Suspendido"),
        ],
        default="draft", tracking=True, copy=False,
    )
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company)

    @api.depends("line_ids.amount", "line_ids.state", "amount")
    def _compute_balance(self):
        for loan in self:
            paid = sum(loan.line_ids.filtered(lambda l: l.state == "paid").mapped("amount"))
            loan.amount_paid = paid
            loan.balance = loan.amount - paid
            if loan.state == "active" and loan.balance <= 0 and loan.line_ids:
                loan.state = "cancelled"

    @api.constrains("amount", "installments")
    def _check_amount(self):
        for loan in self:
            if loan.amount <= 0:
                raise ValidationError("El monto del préstamo/anticipo debe ser mayor que cero.")
            if loan.installments < 1:
                raise ValidationError("El número de cuotas debe ser al menos 1.")

    def action_confirm(self):
        for loan in self:
            if not loan.line_ids:
                loan._generate_plan()
            if loan.name == "Nuevo":
                loan.name = self.env["ir.sequence"].next_by_code("l10n.gt.loan") or "PREST/ANT"
            loan.state = "active"

    def action_suspend(self):
        self.state = "suspended"

    def action_reactivate(self):
        self.filtered(lambda l: l.state == "suspended").state = "active"

    def _generate_plan(self):
        """Genera cuotas iguales mensuales a partir de la fecha de otorgamiento."""
        self.ensure_one()
        self.line_ids.unlink()
        cuota = round(self.amount / self.installments, 2)
        vals = []
        acumulado = 0.0
        for i in range(self.installments):
            monto = cuota if i < self.installments - 1 else (self.amount - acumulado)
            acumulado += monto
            vals.append({
                "loan_id": self.id,
                "sequence": i + 1,
                "due_date": fields.Date.add(self.date_grant, months=i + 1),
                "amount": monto,
            })
        self.env["l10n.gt.loan.line"].create(vals)


class L10nGtLoanLine(models.Model):
    _name = "l10n.gt.loan.line"
    _description = "Cuota de préstamo / anticipo"
    _order = "loan_id, sequence"

    loan_id = fields.Many2one("l10n.gt.loan", required=True, ondelete="cascade")
    sequence = fields.Integer(default=1)
    due_date = fields.Date("Fecha de cuota", required=True)
    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one(related="loan_id.currency_id")
    state = fields.Selection(
        selection=[("pending", "Pendiente"), ("paid", "Pagada")],
        default="pending",
    )
    payslip_id = fields.Many2one("hr.payslip", string="Recibo", copy=False)
    paid_date = fields.Date(copy=False)
