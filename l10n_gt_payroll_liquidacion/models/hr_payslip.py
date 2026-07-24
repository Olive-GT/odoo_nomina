# -*- coding: utf-8 -*-
from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError


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


class HrPayslip(models.Model):
    """Recibo de liquidación (finiquito): un recibo normal cuyo período cierra en
    la fecha de retiro y que, además del salario prorrateado, paga las prestaciones
    proporcionales e indemnización como líneas del Estado de Cuenta (drenando el
    pasivo laboral acumulado). Unifica la liquidación con toda la arquitectura de
    recibos, sin modelo aparte (§4.16, §5)."""

    _inherit = "hr.payslip"

    l10n_gt_is_settlement = fields.Boolean(
        "Recibo de liquidación (finiquito)",
        help="Marca este recibo como finiquito: el período cierra en la fecha de "
             "retiro (no se ajusta al mes completo) y el botón 'Calcular finiquito' "
             "agrega las prestaciones proporcionales y la indemnización.")
    l10n_gt_termination_reason = fields.Selection(
        TERMINATION_REASONS, string="Motivo de finalización")
    l10n_gt_settlement_indemnity = fields.Boolean(
        "Genera indemnización", compute="_compute_l10n_gt_settlement_indemnity",
        store=True, readonly=False)
    l10n_gt_settlement_years = fields.Float(
        "Años laborados", compute="_compute_l10n_gt_settlement_info")
    l10n_gt_settlement_total = fields.Monetary(
        "Total del finiquito", compute="_compute_l10n_gt_settlement_total")

    @api.depends("l10n_gt_termination_reason")
    def _compute_l10n_gt_settlement_indemnity(self):
        for slip in self:
            slip.l10n_gt_settlement_indemnity = (
                slip.l10n_gt_termination_reason in REASONS_WITH_INDEMNITY)

    @api.depends("employee_id", "date_to")
    def _compute_l10n_gt_settlement_info(self):
        for slip in self:
            slip.l10n_gt_settlement_years = slip._l10n_gt_settlement_years_worked()

    @api.depends("l10n_gt_payment_ids.amount", "l10n_gt_payment_ids.benefit_type")
    def _compute_l10n_gt_settlement_total(self):
        for slip in self:
            total = 0.0
            for p in slip.l10n_gt_payment_ids:
                if p.benefit_type == "anticipo_recover":
                    total -= p.amount
                elif p.benefit_type != "anticipo_given":
                    total += p.amount
            slip.l10n_gt_settlement_total = total

    # ------------------------------------------------------------------
    # El período de un finiquito NO se ajusta al mes completo: cierra en date_to.
    # ------------------------------------------------------------------
    @api.onchange("employee_id", "contract_id", "date_from", "date_to")
    def _l10n_gt_snap_full_month(self):
        if self.l10n_gt_is_settlement:
            return
        return super()._l10n_gt_snap_full_month()

    # ------------------------------------------------------------------
    # Cálculo legal (§4.16 / §5) — reutilizado del finiquito
    # ------------------------------------------------------------------
    def _l10n_gt_settlement_start(self):
        self.ensure_one()
        contract = self.contract_id or self.employee_id.contract_id
        return contract.date_start if contract else False

    def _l10n_gt_settlement_years_worked(self):
        self.ensure_one()
        start = self._l10n_gt_settlement_start()
        if not start or not self.date_to:
            return 0.0
        return ((self.date_to - start).days + 1) / 365.0

    def _l10n_gt_six_months_ago(self):
        self.ensure_one()
        d = self.date_to
        month, year = d.month - 6, d.year
        if month <= 0:
            month += 12
            year -= 1
        return date(year, month, 1)

    def _l10n_gt_settlement_prop_benefit(self, benefit_type):
        """Aguinaldo/Bono 14 proporcional pendiente a la fecha de retiro."""
        self.ensure_one()
        start = self._l10n_gt_settlement_start()
        d = self.date_to
        if not start or not d:
            return 0.0
        if benefit_type == "aguinaldo":
            window = date(d.year - 1, 12, 1) if d.month < 12 else date(d.year, 12, 1)
        else:  # bono14
            window = date(d.year - 1, 7, 1) if d.month < 7 else date(d.year, 7, 1)
        employed_days = (d - start).days + 1
        ini = start if employed_days <= 365 else max(window, start)
        if ini > d:
            return 0.0
        dias = (d - ini).days + 1
        promedio = self.employee_id._l10n_gt_average_ordinary(ini, d)
        return promedio * dias / 365.0

    def _l10n_gt_settlement_amounts(self):
        """Montos del finiquito = el pasivo laboral acumulado del empleado (que ya
        incluye los saldos de apertura + lo devengado − lo pagado). Así respeta la
        historia previa configurada, sin depender del sueldo actual."""
        self.ensure_one()
        emp = self.employee_id
        return {
            "aguinaldo": emp.l10n_gt_liab_aguinaldo,
            "bono14": emp.l10n_gt_liab_bono14,
            "vacaciones": emp.l10n_gt_liab_vacaciones,
            "indemnizacion": (emp.l10n_gt_liab_indemnizacion
                              if self.l10n_gt_settlement_indemnity else 0.0),
        }

    def action_l10n_gt_compute_settlement(self):
        """Calcula el finiquito y crea las líneas de pago: salario prorrateado (neto)
        + prestaciones proporcionales + indemnización (drenan el pasivo laboral)."""
        self.ensure_one()
        if not self.l10n_gt_is_settlement:
            raise UserError("Marca primero 'Recibo de liquidación (finiquito)'.")
        if not self._l10n_gt_settlement_start() or not self.date_to:
            raise UserError("Configura el empleado con contrato y la fecha de retiro "
                            "(fin del período).")
        Payment = self.env["l10n.gt.payslip.payment"]
        d = self.date_to
        amounts = self._l10n_gt_settlement_amounts()
        # Regenera solo lo NO pagado (salario + prestaciones del finiquito).
        tipos = ("salary", "aguinaldo", "bono14", "vacaciones", "indemnizacion")
        self.l10n_gt_payment_ids.filtered(
            lambda p: not p.paid and p.benefit_type in tipos).unlink()
        # Salario neto prorrateado (una sola línea de finiquito).
        net = self._l10n_gt_line("NET")
        if net > 0:
            Payment.create({
                "payslip_id": self.id, "name": "Liquidación de salario",
                "date": d, "amount": round(net, 2), "benefit_type": "salary",
            })
        # Prestaciones proporcionales e indemnización.
        etiquetas = {
            "aguinaldo": "Aguinaldo proporcional",
            "bono14": "Bono 14 proporcional",
            "vacaciones": "Vacaciones pendientes",
            "indemnizacion": "Indemnización",
        }
        for btype in ("aguinaldo", "bono14", "vacaciones", "indemnizacion"):
            monto = round(amounts.get(btype, 0.0), 2)
            if monto > 0:
                Payment.create({
                    "payslip_id": self.id, "name": etiquetas[btype], "date": d,
                    "amount": monto, "benefit_type": btype,
                })
        return True

    def _l10n_gt_sum_payments(self, btype):
        """Suma de líneas de pago de un tipo (para el reporte de finiquito)."""
        self.ensure_one()
        return sum(self.l10n_gt_payment_ids.filtered(
            lambda p: p.benefit_type == btype).mapped("amount"))

    def action_payslip_done(self):
        """Al confirmar un finiquito, cierra el contrato y desactiva al empleado
        (conserva historial, §5.6)."""
        res = super().action_payslip_done()
        for slip in self.filtered("l10n_gt_is_settlement"):
            if slip.contract_id:
                slip.contract_id.write({
                    "date_end": slip.date_to, "state": "close"})
            slip.employee_id.active = False
        return res
