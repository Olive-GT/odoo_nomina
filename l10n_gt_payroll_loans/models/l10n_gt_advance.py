# -*- coding: utf-8 -*-
from odoo import api, fields, models


class L10nGtAdvance(models.Model):
    """Anticipo de sueldo flexible: se entrega dinero al empleado y se recupera
    (descuenta) cuando la empresa lo decida, total o parcialmente, en cualquier
    recibo posterior. Mantiene un saldo pendiente hasta quedar saldado."""

    _name = "l10n.gt.advance"
    _description = "Anticipo de sueldo"
    _inherit = ["mail.thread"]
    _order = "date desc, id desc"

    name = fields.Char(default="Nuevo", copy=False)
    employee_id = fields.Many2one(
        "hr.employee", string="Empleado", required=True, ondelete="restrict",
        tracking=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company)
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda s: s.env.ref("base.GTQ", raise_if_not_found=False))
    date = fields.Date(
        "Fecha de entrega", required=True, default=fields.Date.context_today,
        tracking=True)
    amount = fields.Monetary("Monto entregado", required=True, tracking=True)
    reference = fields.Char("Referencia / motivo")
    recovery_ids = fields.One2many(
        "l10n.gt.advance.recovery", "advance_id", string="Devoluciones")
    amount_recovered = fields.Monetary(
        "Devuelto", compute="_compute_balance", store=True)
    balance = fields.Monetary(
        "Saldo pendiente", compute="_compute_balance", store=True)
    state = fields.Selection(
        selection=[("pending", "Pendiente"), ("recovered", "Saldado")],
        compute="_compute_balance", store=True, default="pending")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == "Nuevo":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "l10n.gt.advance") or "Anticipo"
        return super().create(vals_list)

    @api.depends("amount", "recovery_ids.amount")
    def _compute_balance(self):
        for rec in self:
            rec.amount_recovered = sum(rec.recovery_ids.mapped("amount"))
            rec.balance = rec.amount - rec.amount_recovered
            rec.state = "recovered" if rec.balance <= 0.005 else "pending"


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_gt_advance_ids = fields.One2many(
        "l10n.gt.advance", "employee_id", string="Anticipos")


class L10nGtAdvanceRecovery(models.Model):
    """Cada devolución (descuento) de un anticipo, ligada al recibo que lo aplicó."""

    _name = "l10n.gt.advance.recovery"
    _description = "Devolución de anticipo"
    _order = "date, id"

    advance_id = fields.Many2one(
        "l10n.gt.advance", string="Anticipo", required=True, ondelete="cascade")
    employee_id = fields.Many2one(
        related="advance_id.employee_id", store=True)
    payslip_id = fields.Many2one("hr.payslip", string="Recibo", ondelete="set null")
    company_id = fields.Many2one(related="advance_id.company_id", store=True)
    currency_id = fields.Many2one(related="advance_id.currency_id")
    date = fields.Date("Fecha", required=True, default=fields.Date.context_today)
    amount = fields.Monetary("Monto devuelto", required=True)
