# -*- coding: utf-8 -*-
from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError


class L10nGtBenefitRun(models.Model):
    """Planilla independiente de Aguinaldo / Bono 14 (§4.7.4, §4.8.4, §6.3, §6.4)."""

    _name = "l10n.gt.benefit.run"
    _description = "Planilla de Aguinaldo / Bono 14"
    _order = "year desc"

    name = fields.Char(compute="_compute_name", store=True)
    benefit_type = fields.Selection(
        selection=[("aguinaldo", "Aguinaldo"), ("bono14", "Bono 14")],
        string="Prestación", required=True, default="aguinaldo",
    )
    year = fields.Integer(required=True, default=lambda s: fields.Date.today().year)
    date_from = fields.Date(compute="_compute_window", store=True)
    date_to = fields.Date(compute="_compute_window", store=True)
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company)
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.ref("base.GTQ", raise_if_not_found=False),
    )
    state = fields.Selection(
        selection=[("draft", "Borrador"), ("computed", "Calculado"),
                   ("confirmed", "Confirmado")],
        default="draft", tracking=True, copy=False,
    )
    line_ids = fields.One2many("l10n.gt.benefit.line", "run_id", string="Detalle")
    total_amount = fields.Monetary(compute="_compute_total", store=True)

    @api.depends("benefit_type", "year")
    def _compute_name(self):
        labels = dict(self._fields["benefit_type"].selection)
        for rec in self:
            rec.name = "%s %s" % (labels.get(rec.benefit_type, ""), rec.year or "")

    @api.depends("benefit_type", "year")
    def _compute_window(self):
        """Aguinaldo: 01-dic (año-1) a 30-nov. Bono 14: 01-jul (año-1) a 30-jun."""
        for rec in self:
            if not rec.year:
                rec.date_from = rec.date_to = False
                continue
            if rec.benefit_type == "aguinaldo":
                rec.date_from = date(rec.year - 1, 12, 1)
                rec.date_to = date(rec.year, 11, 30)
            else:
                rec.date_from = date(rec.year - 1, 7, 1)
                rec.date_to = date(rec.year, 6, 30)

    @api.depends("line_ids.amount")
    def _compute_total(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped("amount"))

    def action_compute(self):
        """Calcula la prestación para todos los empleados activos con contrato."""
        Line = self.env["l10n.gt.benefit.line"]
        for rec in self:
            rec.line_ids.unlink()
            employees = self.env["hr.employee"].search([
                ("company_id", "=", rec.company_id.id),
            ])
            vals = []
            for emp in employees:
                if not emp.contract_id or not emp.contract_id.date_start:
                    continue
                if emp.contract_id.date_start > rec.date_to:
                    continue
                worked = emp._l10n_gt_worked_days_between(rec.date_from, rec.date_to)
                if worked <= 0:
                    continue
                promedio = emp._l10n_gt_average_ordinary(rec.date_from, rec.date_to)
                amount = promedio * worked / 365.0
                vals.append({
                    "run_id": rec.id,
                    "employee_id": emp.id,
                    "date_start": emp.contract_id.date_start,
                    "worked_days": worked,
                    "average_salary": promedio,
                    "amount_full": promedio,
                    "amount": amount,
                })
            if not vals:
                raise UserError("No hay empleados con relación laboral en la ventana.")
            Line.create(vals)
            rec.state = "computed"

    def action_confirm(self):
        self.state = "confirmed"


class L10nGtBenefitLine(models.Model):
    _name = "l10n.gt.benefit.line"
    _description = "Detalle de planilla de prestación"
    _order = "run_id, employee_id"

    run_id = fields.Many2one("l10n.gt.benefit.run", required=True, ondelete="cascade")
    employee_id = fields.Many2one("hr.employee", required=True)
    currency_id = fields.Many2one(related="run_id.currency_id")
    date_start = fields.Date("Fecha de ingreso")
    worked_days = fields.Integer("Días laborados (ventana)")
    average_salary = fields.Monetary("Salario promedio")
    amount_full = fields.Monetary("Prestación completa")
    amount = fields.Monetary("Monto (proporcional)")
    dpi = fields.Char(related="employee_id.l10n_gt_dpi", string="DPI")
