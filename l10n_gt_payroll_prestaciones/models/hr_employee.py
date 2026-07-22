# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_gt_vacation_taken_ids = fields.One2many(
        "l10n.gt.vacation.taken", "employee_id", string="Vacaciones gozadas",
    )

    # ------------------------------------------------------------------
    # Pasivo laboral acumulado (provisiones por pagar)
    # ------------------------------------------------------------------
    l10n_gt_currency_id = fields.Many2one(
        related="company_id.currency_id", string="Moneda")
    l10n_gt_liab_aguinaldo = fields.Monetary(
        "Aguinaldo por pagar", compute="_compute_labor_liability",
        currency_field="l10n_gt_currency_id")
    l10n_gt_liab_bono14 = fields.Monetary(
        "Bono 14 por pagar", compute="_compute_labor_liability",
        currency_field="l10n_gt_currency_id")
    l10n_gt_liab_indemnizacion = fields.Monetary(
        "Indemnización acumulada", compute="_compute_labor_liability",
        currency_field="l10n_gt_currency_id")
    l10n_gt_liab_vacaciones = fields.Monetary(
        "Vacaciones por pagar", compute="_compute_labor_liability",
        currency_field="l10n_gt_currency_id")
    l10n_gt_liab_total = fields.Monetary(
        "Pasivo laboral total", compute="_compute_labor_liability",
        currency_field="l10n_gt_currency_id")

    def _l10n_gt_sum_provision(self, code):
        """Suma de una provisión (PROVAGUI/PROVBONO14/PROVINDEM) devengada en las
        nóminas ya confirmadas del empleado. A futuro se le restarán los pagos que
        dren el pasivo (cuando se pague la prestación)."""
        self.ensure_one()
        lines = self.env["hr.payslip.line"].search([
            ("slip_id.employee_id", "=", self.id),
            ("slip_id.state", "in", ("done", "paid")),
            ("code", "=", code),
        ])
        return sum(lines.mapped("total"))

    @api.depends("l10n_gt_vacation_taken_ids.days")
    def _compute_labor_liability(self):
        today = fields.Date.today()
        for emp in self:
            emp.l10n_gt_liab_aguinaldo = emp._l10n_gt_sum_provision("PROVAGUI")
            emp.l10n_gt_liab_bono14 = emp._l10n_gt_sum_provision("PROVBONO14")
            emp.l10n_gt_liab_indemnizacion = emp._l10n_gt_sum_provision("PROVINDEM")
            dias_pend = emp._l10n_gt_vacation_pending_at(today)
            daily = emp._l10n_gt_daily_average(today - timedelta(days=365), today)
            emp.l10n_gt_liab_vacaciones = dias_pend * daily
            emp.l10n_gt_liab_total = (
                emp.l10n_gt_liab_aguinaldo + emp.l10n_gt_liab_bono14
                + emp.l10n_gt_liab_indemnizacion + emp.l10n_gt_liab_vacaciones
            )
    l10n_gt_vacation_accrued = fields.Float(
        "Días de vacaciones acumulados", compute="_compute_vacation", store=False,
    )
    l10n_gt_vacation_taken = fields.Float(
        "Días de vacaciones gozados", compute="_compute_vacation", store=False,
    )
    l10n_gt_vacation_pending = fields.Float(
        "Días de vacaciones pendientes", compute="_compute_vacation", store=False,
    )

    # ------------------------------------------------------------------
    # Salario ordinario promedio (base de prestaciones §4.6/4.7/4.8/4.16)
    # ------------------------------------------------------------------
    def _l10n_gt_worked_days_between(self, date_from, date_to):
        """Días de relación laboral dentro de la ventana [date_from, date_to]."""
        self.ensure_one()
        contracts = self.env["hr.contract"].search([
            ("employee_id", "=", self.id),
            ("state", "in", ("open", "close")),
            ("date_start", "<=", date_to),
            "|", ("date_end", "=", False), ("date_end", ">=", date_from),
        ])
        if not contracts:
            return 0
        ini = max(date_from, min(contracts.mapped("date_start")))
        fechas_fin = [c.date_end or date_to for c in contracts]
        fin = min(date_to, max(fechas_fin))
        return max(0, (fin - ini).days + 1)

    def _l10n_gt_average_ordinary(self, date_from, date_to):
        """Promedio del salario ordinario mensual, ponderado por días de
        vigencia de cada contrato en la ventana (§4.7.2, §4.8.2)."""
        self.ensure_one()
        contracts = self.env["hr.contract"].search([
            ("employee_id", "=", self.id),
            ("state", "in", ("open", "close")),
            ("date_start", "<=", date_to),
            "|", ("date_end", "=", False), ("date_end", ">=", date_from),
        ])
        total_dias, ponderado = 0, 0.0
        for c in contracts:
            ini = max(date_from, c.date_start)
            fin = min(date_to, c.date_end or date_to)
            dias = (fin - ini).days + 1
            if dias <= 0:
                continue
            total_dias += dias
            ponderado += c.wage * dias
        if total_dias:
            return ponderado / total_dias
        return self.contract_id.wage if self.contract_id else 0.0

    def _l10n_gt_daily_average(self, date_from, date_to):
        """Sueldo diario promedio = salario mensual promedio x 12 / 365.

        Base diaria guatemalteca para vacaciones e indemnización (anexo 8.6:
        Q276.16 para un salario de Q8,000)."""
        self.ensure_one()
        return self._l10n_gt_average_ordinary(date_from, date_to) * 12.0 / 365.0

    # ------------------------------------------------------------------
    # Vacaciones (§4.6, §6.13): 15 días hábiles por año de servicio
    # ------------------------------------------------------------------
    @api.depends("l10n_gt_vacation_taken_ids.days")
    def _compute_vacation(self):
        today = fields.Date.today()
        for emp in self:
            emp.l10n_gt_vacation_accrued = emp._l10n_gt_vacation_accrued_at(today)
            emp.l10n_gt_vacation_taken = sum(emp.l10n_gt_vacation_taken_ids.mapped("days"))
            emp.l10n_gt_vacation_pending = (
                emp.l10n_gt_vacation_accrued - emp.l10n_gt_vacation_taken
            )

    def _l10n_gt_vacation_accrued_at(self, date_ref):
        """Días de vacaciones acumulados a una fecha de corte (15 días/año)."""
        self.ensure_one()
        start = self.contract_id.date_start if self.contract_id else False
        if not start or not date_ref:
            return 0.0
        anios = ((date_ref - start).days + 1) / 365.0
        return round(anios * 15.0, 2)

    def _l10n_gt_vacation_pending_at(self, date_ref):
        """Días pendientes a una fecha de corte (para liquidaciones §4.6)."""
        self.ensure_one()
        accrued = self._l10n_gt_vacation_accrued_at(date_ref)
        taken = sum(
            t.days for t in self.l10n_gt_vacation_taken_ids
            if t.date_to and t.date_to <= date_ref
        )
        return max(0.0, accrued - taken)


class L10nGtVacationTaken(models.Model):
    _name = "l10n.gt.vacation.taken"
    _description = "Período vacacional gozado"
    _order = "date_from desc"

    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")
    date_from = fields.Date("Desde", required=True)
    date_to = fields.Date("Hasta", required=True)
    days = fields.Float("Días gozados", required=True)
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company)
