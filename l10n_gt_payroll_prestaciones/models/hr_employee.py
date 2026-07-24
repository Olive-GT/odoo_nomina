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

    # ------------------------------------------------------------------
    # Saldos de apertura (al adoptar el módulo con historia previa)
    # ------------------------------------------------------------------
    l10n_gt_opening_date = fields.Date(
        "Fecha de corte (apertura)",
        help="Fecha desde la que este módulo empieza a acumular. Los saldos de "
             "apertura representan lo acumulado ANTES de esta fecha (con los "
             "sueldos históricos que hayan sido). De aquí en adelante el sistema "
             "sigue acumulando solo.")
    l10n_gt_opening_aguinaldo = fields.Monetary(
        "Aguinaldo acumulado (apertura)", currency_field="l10n_gt_currency_id")
    l10n_gt_opening_bono14 = fields.Monetary(
        "Bono 14 acumulado (apertura)", currency_field="l10n_gt_currency_id")
    l10n_gt_opening_indemnizacion = fields.Monetary(
        "Indemnización acumulada (apertura)", currency_field="l10n_gt_currency_id")
    l10n_gt_opening_vacation_days = fields.Float(
        "Vacaciones pendientes a la apertura (días)",
        help="Días de vacaciones pendientes (ya netos de las gozadas) a la fecha de "
             "corte. De aquí en adelante se acumulan 15/año y se restan las gozadas "
             "que registres después de la fecha de corte.")

    def _l10n_gt_sum_provision(self, code):
        """Suma de una provisión (PROVAGUI/PROVBONO14/PROVINDEM) devengada en las
        nóminas ya confirmadas del empleado."""
        self.ensure_one()
        lines = self.env["hr.payslip.line"].search([
            ("slip_id.employee_id", "=", self.id),
            ("slip_id.state", "in", ("done", "paid")),
            ("code", "=", code),
        ])
        return sum(lines.mapped("total"))

    def _l10n_gt_sum_benefit_paid(self, benefit_type):
        """Suma de pagos de una prestación (marcados como Pagados) que drenan el
        pasivo acumulado."""
        self.ensure_one()
        payments = self.env["l10n.gt.payslip.payment"].search([
            ("payslip_id.employee_id", "=", self.id),
            ("benefit_type", "=", benefit_type),
            ("paid", "=", True),
        ])
        return sum(payments.mapped("amount"))

    # ------------------------------------------------------------------
    # Monto pagable de la prestación en su PERÍODO legal (§4.7 / §4.8)
    # ------------------------------------------------------------------
    def _l10n_gt_benefit_window(self, benefit_type, ref_date):
        """Ventana [inicio, fin] del período de la prestación que se paga
        alrededor de ref_date.
        - Bono 14: 1-jul (año-1) a 30-jun; se paga en julio.
        - Aguinaldo: 1-dic (año-1) a 30-nov; se paga en dic/ene."""
        y = ref_date.year
        if benefit_type == "bono14":
            pe = y if ref_date.month >= 7 else y - 1
            return date(pe - 1, 7, 1), date(pe, 6, 30)
        if benefit_type == "aguinaldo":
            pe = y if ref_date.month >= 12 else y - 1
            return date(pe - 1, 12, 1), date(pe, 11, 30)
        return None, None

    def _l10n_gt_sum_provision_window(self, code, date_from, date_to):
        """Provisión devengada de recibos confirmados cuyo período (date_to) cae
        dentro de la ventana [date_from, date_to]."""
        self.ensure_one()
        lines = self.env["hr.payslip.line"].search([
            ("slip_id.employee_id", "=", self.id),
            ("slip_id.state", "in", ("done", "paid")),
            ("code", "=", code),
            ("slip_id.date_to", ">=", date_from),
            ("slip_id.date_to", "<=", date_to),
        ])
        return sum(lines.mapped("total"))

    def _l10n_gt_benefit_payable(self, benefit_type, ref_date):
        """Monto legal a pagar de la prestación en su período actual:
        provisión devengada dentro de la ventana − lo ya pagado por ESE período.

        Así la provisión del mes siguiente (que pertenece al período del año
        entrante) no se incluye por error."""
        self.ensure_one()
        code = {"bono14": "PROVBONO14", "aguinaldo": "PROVAGUI"}.get(benefit_type)
        if not code:
            return 0.0
        win_start, win_end = self._l10n_gt_benefit_window(benefit_type, ref_date)
        accrued = self._l10n_gt_sum_provision_window(code, win_start, win_end)
        # Saldo de apertura: se suma SOLO en la ventana que contiene la fecha de
        # corte (la primera tras adoptar el módulo); en ventanas posteriores ya no.
        if (self.l10n_gt_opening_date
                and win_start <= self.l10n_gt_opening_date <= win_end):
            accrued += (self.l10n_gt_opening_aguinaldo if benefit_type == "aguinaldo"
                        else self.l10n_gt_opening_bono14)
        # Pagos ya hechos para ESTE período (posteriores a su cierre y antes del
        # cierre del período siguiente).
        next_end = date(win_end.year + 1, win_end.month, win_end.day)
        payments = self.env["l10n.gt.payslip.payment"].search([
            ("payslip_id.employee_id", "=", self.id),
            ("benefit_type", "=", benefit_type),
            ("paid", "=", True),
            ("date", ">", win_end),
            ("date", "<=", next_end),
        ])
        return max(accrued - sum(payments.mapped("amount")), 0.0)

    @api.depends("l10n_gt_vacation_taken_ids.days", "l10n_gt_opening_date",
                 "l10n_gt_opening_aguinaldo", "l10n_gt_opening_bono14",
                 "l10n_gt_opening_indemnizacion", "l10n_gt_opening_vacation_days")
    def _compute_labor_liability(self):
        today = fields.Date.today()
        for emp in self:
            # Pasivo = saldo de apertura + provisiones devengadas − lo ya pagado.
            emp.l10n_gt_liab_aguinaldo = (
                emp.l10n_gt_opening_aguinaldo
                + emp._l10n_gt_sum_provision("PROVAGUI")
                - emp._l10n_gt_sum_benefit_paid("aguinaldo"))
            emp.l10n_gt_liab_bono14 = (
                emp.l10n_gt_opening_bono14
                + emp._l10n_gt_sum_provision("PROVBONO14")
                - emp._l10n_gt_sum_benefit_paid("bono14"))
            # Indemnización: apertura + provisiones acumuladas − pagado.
            emp.l10n_gt_liab_indemnizacion = (
                emp.l10n_gt_opening_indemnizacion
                + emp._l10n_gt_sum_provision("PROVINDEM")
                - emp._l10n_gt_sum_benefit_paid("indemnizacion"))
            dias_pend = emp._l10n_gt_vacation_pending_at(today)
            daily = emp._l10n_gt_daily_average(today - timedelta(days=365), today)
            emp.l10n_gt_liab_vacaciones = (
                dias_pend * daily - emp._l10n_gt_sum_benefit_paid("vacaciones"))
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
        """Días de vacaciones acumulados a una fecha (15 días/año).

        Con saldo de apertura: parte de los días pendientes a la fecha de corte y
        acumula 15/año desde ahí. Sin apertura: acumula desde la fecha de ingreso.
        """
        self.ensure_one()
        if not date_ref:
            return 0.0
        if self.l10n_gt_opening_date:
            # Parte de los días pendientes a la apertura y acumula 15/año desde la
            # fecha de corte (sin acumulación negativa si la fecha aún no llega).
            anios = max((date_ref - self.l10n_gt_opening_date).days, 0) / 365.0
            return round((self.l10n_gt_opening_vacation_days or 0.0) + anios * 15.0, 2)
        start = self.contract_id.date_start if self.contract_id else False
        if not start:
            return 0.0
        anios = ((date_ref - start).days + 1) / 365.0
        return round(anios * 15.0, 2)

    def _l10n_gt_vacation_pending_at(self, date_ref):
        """Días pendientes a una fecha de corte (para liquidaciones §4.6).

        Con apertura, solo cuenta las gozadas posteriores a la fecha de corte (las
        anteriores ya están netas en el saldo de apertura)."""
        self.ensure_one()
        accrued = self._l10n_gt_vacation_accrued_at(date_ref)
        opening = self.l10n_gt_opening_date
        taken = sum(
            t.days for t in self.l10n_gt_vacation_taken_ids
            if t.date_to and t.date_to <= date_ref
            and (not opening or t.date_to >= opening)
        )
        return max(0.0, accrued - taken)


class L10nGtVacationTaken(models.Model):
    _name = "l10n.gt.vacation.taken"
    _description = "Período vacacional gozado"
    _order = "date_from desc"

    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")
    date_from = fields.Date("Desde", required=True)
    date_to = fields.Date("Hasta", required=True)
    days = fields.Float("Días gozados", required=True,
                        help="Admite medios (0.5) y cuartos (0.25) de día.")
    payslip_id = fields.Many2one("hr.payslip", string="Recibo", ondelete="set null")
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company)
