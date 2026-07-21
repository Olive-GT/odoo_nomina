# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


TERMINATION_REASONS = [
    ("despido_injustificado", "Despido injustificado"),
    ("despido_justificado", "Despido justificado"),
    ("renuncia", "Renuncia"),
    ("mutuo_acuerdo", "Mutuo acuerdo"),
    ("vencimiento", "Vencimiento de contrato"),
    ("fallecimiento", "Fallecimiento"),
]

# Motivos que generan derecho a indemnización (§4.16.4)
REASONS_WITH_INDEMNITY = {"despido_injustificado", "mutuo_acuerdo", "fallecimiento"}


class L10nGtSettlement(models.Model):
    """Liquidación laboral (§5) con indemnización (§4.16). Estados de §7.9.2."""

    _name = "l10n.gt.settlement"
    _description = "Liquidación laboral"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_end desc"

    name = fields.Char(default="Nuevo", copy=False)
    employee_id = fields.Many2one(
        "hr.employee", required=True, ondelete="restrict", tracking=True,
    )
    contract_id = fields.Many2one("hr.contract", string="Contrato")
    date_start = fields.Date("Fecha de ingreso", compute="_compute_dates", store=True, readonly=False)
    date_end = fields.Date("Fecha de retiro", required=True, tracking=True)
    last_worked_day = fields.Date("Último día laborado")
    payment_date = fields.Date("Fecha de pago")
    reason = fields.Selection(TERMINATION_REASONS, string="Motivo de finalización",
                              required=True, tracking=True)
    has_indemnity = fields.Boolean("Genera indemnización", compute="_compute_has_indemnity",
                                   store=True, readonly=False)
    notes = fields.Text("Observaciones")
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company)
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.ref("base.GTQ", raise_if_not_found=False),
    )
    state = fields.Selection(
        selection=[
            ("draft", "Borrador"), ("computed", "Calculada"), ("approved", "Aprobada"),
            ("paid", "Pagada"), ("cancelled", "Anulada"),
        ],
        default="draft", tracking=True, copy=False,
    )

    # --- Conceptos calculados (§5.3) ---
    years_worked = fields.Float("Años laborados", readonly=True)
    daily_wage = fields.Monetary("Sueldo diario", readonly=True)
    average_salary = fields.Monetary("Salario promedio (6 meses)", readonly=True)

    salario_pendiente = fields.Monetary("Salario ordinario pendiente", readonly=True)
    bonif_pendiente = fields.Monetary("Bonificación incentivo pendiente", readonly=True)
    aguinaldo_prop = fields.Monetary("Aguinaldo proporcional", readonly=True)
    bono14_prop = fields.Monetary("Bono 14 proporcional", readonly=True)
    vacaciones = fields.Monetary("Vacaciones pendientes", readonly=True)
    indemnizacion = fields.Monetary("Indemnización", readonly=True)

    igss_pendiente = fields.Monetary("IGSS laboral", readonly=True)
    isr_pendiente = fields.Monetary("ISR", readonly=True)
    anticipos_pendientes = fields.Monetary("Anticipos pendientes", readonly=True)
    prestamos_pendientes = fields.Monetary("Préstamos pendientes", readonly=True)

    total_ingresos = fields.Monetary("Total prestaciones e ingresos", readonly=True)
    total_descuentos = fields.Monetary("Total descuentos", readonly=True)
    total_liquidacion = fields.Monetary("Total liquidación a pagar", readonly=True)

    _sql_constraints = [
        ("employee_date_uniq", "unique(employee_id, date_end, company_id)",
         "Ya existe una liquidación para este empleado y fecha de retiro (§5.6)."),
    ]

    @api.depends("employee_id")
    def _compute_dates(self):
        for rec in self:
            contract = rec.employee_id.contract_id
            rec.contract_id = contract
            rec.date_start = contract.date_start if contract else False

    @api.depends("reason")
    def _compute_has_indemnity(self):
        for rec in self:
            rec.has_indemnity = rec.reason in REASONS_WITH_INDEMNITY

    def _get_param(self, code):
        return self.env["hr.rule.parameter"]._get_parameter_from_code(
            code, self.date_end or fields.Date.today()
        )

    # ------------------------------------------------------------------
    # Cálculo (§5.4)
    # ------------------------------------------------------------------
    def action_compute(self):
        for rec in self:
            rec._compute_settlement()
            rec.state = "computed"
        return True

    def _compute_settlement(self):
        self.ensure_one()
        emp = self.employee_id
        contract = self.contract_id or emp.contract_id
        if not contract or not self.date_start or not self.date_end:
            raise UserError("Configure empleado, fecha de ingreso y fecha de retiro.")
        if self.date_end < self.date_start:
            raise ValidationError("La fecha de retiro no puede ser anterior al ingreso.")

        wage = contract.wage
        self.years_worked = ((self.date_end - self.date_start).days + 1) / 365.0
        self.daily_wage = wage / 30.0
        igss_tasa = self._get_param("l10n_gt_igss_laboral")

        # --- Salario ordinario y bonificación pendientes del mes de baja ---
        month_start = self.date_end.replace(day=1)
        last_slip = self.env["hr.payslip"].search([
            ("employee_id", "=", emp.id), ("state", "=", "done"),
            ("date_to", "<", self.date_end),
        ], order="date_to desc", limit=1)
        tramo_ini = month_start
        if last_slip and last_slip.date_to >= month_start:
            tramo_ini = last_slip.date_to + timedelta(days=1)
        if self.date_start > tramo_ini:
            tramo_ini = self.date_start
        dias_pend = max(0, (self.date_end - tramo_ini).days + 1)
        self.salario_pendiente = self.daily_wage * dias_pend
        bonif_mensual = contract.l10n_gt_bonif_incentivo or self._get_param(
            "l10n_gt_bonif_incentivo_min")
        self.bonif_pendiente = (bonif_mensual / 30.0) * dias_pend

        # --- Aguinaldo y Bono 14 proporcionales (§5.3) ---
        self.aguinaldo_prop = self._prop_benefit("aguinaldo")
        self.bono14_prop = self._prop_benefit("bono14")

        # --- Vacaciones pendientes (§4.6) ---
        dias_vac = max(0.0, emp.l10n_gt_vacation_pending)
        daily_avg = emp._l10n_gt_daily_average(
            self._six_months_ago(), self.date_end)
        self.vacaciones = dias_vac * daily_avg

        # --- Indemnización (§4.16) ---
        if self.has_indemnity:
            self.average_salary = emp._l10n_gt_average_ordinary(
                self._six_months_ago(), self.date_end)
            salario_indemnizable = self.average_salary + self.average_salary / 12.0 * 2
            self.indemnizacion = salario_indemnizable * self.years_worked
        else:
            self.average_salary = 0.0
            self.indemnizacion = 0.0

        # --- Descuentos ---
        self.igss_pendiente = self.salario_pendiente * igss_tasa
        self.isr_pendiente = 0.0
        self.anticipos_pendientes = self._pending_loans("advance")
        self.prestamos_pendientes = self._pending_loans("loan")

        # --- Totales ---
        self.total_ingresos = (
            self.salario_pendiente + self.bonif_pendiente + self.aguinaldo_prop
            + self.bono14_prop + self.vacaciones + self.indemnizacion
        )
        self.total_descuentos = (
            self.igss_pendiente + self.isr_pendiente
            + self.anticipos_pendientes + self.prestamos_pendientes
        )
        self.total_liquidacion = self.total_ingresos - self.total_descuentos

    def _six_months_ago(self):
        d = self.date_end
        month = d.month - 6
        year = d.year
        if month <= 0:
            month += 12
            year -= 1
        return date(year, month, 1)

    def _prop_benefit(self, benefit_type):
        """Aguinaldo/Bono 14 proporcional pendiente a la fecha de retiro.

        Empleados con menos de un año acumulan desde su ingreso (aún no han
        recibido pago de la prestación). Con más de un año se acumula desde el
        inicio de la ventana de acumulación vigente (el pago anterior ya se hizo).
        """
        self.ensure_one()
        d = self.date_end
        if benefit_type == "aguinaldo":
            window_start = date(d.year - 1, 12, 1) if d.month < 12 else date(d.year, 12, 1)
        else:  # bono14
            window_start = date(d.year - 1, 7, 1) if d.month < 7 else date(d.year, 7, 1)
        employed_days = (d - self.date_start).days + 1
        if employed_days <= 365:
            ini = self.date_start
        else:
            ini = max(window_start, self.date_start)
        if ini > d:
            return 0.0
        dias = (d - ini).days + 1
        promedio = self.employee_id._l10n_gt_average_ordinary(ini, d)
        return promedio * dias / 365.0

    def _pending_loans(self, loan_type):
        # Dependencia opcional del módulo de préstamos/anticipos.
        if "l10n.gt.loan" not in self.env:
            return 0.0
        loans = self.env["l10n.gt.loan"].search([
            ("employee_id", "=", self.employee_id.id),
            ("loan_type", "=", loan_type),
            ("state", "=", "active"),
        ])
        return sum(loans.mapped("balance"))

    # ------------------------------------------------------------------
    # Flujo de estados (§7.9.2)
    # ------------------------------------------------------------------
    def action_approve(self):
        for rec in self:
            if rec.state != "computed":
                raise UserError("Solo se pueden aprobar liquidaciones calculadas.")
            if rec.name == "Nuevo":
                rec.name = self.env["ir.sequence"].next_by_code(
                    "l10n.gt.settlement") or "LIQ"
            rec.state = "approved"
            # §5.6 el empleado pasa a inactivo conservando su historial
            rec.employee_id.active = False
            if rec.contract_id:
                rec.contract_id.write({"date_end": rec.date_end, "state": "close"})

    def action_pay(self):
        self.filtered(lambda r: r.state == "approved").state = "paid"

    def action_cancel(self):
        for rec in self:
            rec.state = "cancelled"
            rec.employee_id.active = True

    def action_draft(self):
        self.state = "draft"
