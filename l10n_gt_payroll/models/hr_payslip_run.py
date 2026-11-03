# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrPayslipRun(models.Model):
    """Período de nómina (§3.2) con el flujo de estados de §7.9.1."""

    _inherit = "hr.payslip.run"

    l10n_gt_structure_type_id = fields.Many2one(
        "hr.payroll.structure.type", string="Tipo de nómina",
    )
    l10n_gt_state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("computing", "En cálculo"),
            ("computed", "Calculado"),
            ("confirmed", "Confirmado"),
            ("posted", "Contabilizado"),
            ("closed", "Cerrado"),
        ],
        string="Estado (GT)",
        default="draft",
        tracking=True,
        copy=False,
    )

    # ------------------------------------------------------------------
    # Validaciones (§3.2.3)
    # ------------------------------------------------------------------
    @api.constrains("date_start", "date_end", "l10n_gt_structure_type_id", "company_id")
    def _check_no_overlap(self):
        """No permitir fechas traslapadas para el mismo tipo de nómina."""
        for run in self.filtered("l10n_gt_structure_type_id"):
            overlap = self.search([
                ("id", "!=", run.id),
                ("company_id", "=", run.company_id.id),
                ("l10n_gt_structure_type_id", "=", run.l10n_gt_structure_type_id.id),
                ("date_start", "<=", run.date_end),
                ("date_end", ">=", run.date_start),
            ], limit=1)
            if overlap:
                raise ValidationError(
                    "Ya existe un período (%s) que se traslapa con las fechas de "
                    "este período para el tipo de nómina '%s' (§3.2.3)." % (
                        overlap.name, run.l10n_gt_structure_type_id.name,
                    )
                )

    # ------------------------------------------------------------------
    # Un lote GT = un mes calendario (IGSS e ISR son mensuales)
    # ------------------------------------------------------------------
    @api.onchange("date_start")
    def _l10n_gt_onchange_date_start(self):
        """Al elegir el inicio, el fin pasa al último día de ese mes. (Odoo pone por
        defecto el fin del mes EN CURSO: si se crea en noviembre el lote de octubre
        y solo se cambia el inicio, quedaba del 01/10 al 30/11.)"""
        if self.date_start:
            self.date_end = self.date_start + relativedelta(day=31)

    def _l10n_gt_check_single_month(self):
        for run in self:
            if run.date_start and run.date_end and (
                    (run.date_start.year, run.date_start.month)
                    != (run.date_end.year, run.date_end.month)):
                raise UserError(
                    "El lote «%s» va del %s al %s y abarca más de un mes. La nómina "
                    "GT se calcula por mes: corrige la fecha final del lote al último "
                    "día del mes (%s) y vuelve a generar los recibos." % (
                        run.name, run.date_start.strftime("%d/%m/%Y"),
                        run.date_end.strftime("%d/%m/%Y"),
                        (run.date_start + relativedelta(day=31)).strftime("%d/%m/%Y")))

    @api.constrains("date_start", "date_end")
    def _l10n_gt_constrain_single_month(self):
        try:
            self._l10n_gt_check_single_month()
        except UserError as e:
            raise ValidationError(e.args[0])

    # ------------------------------------------------------------------
    # Transiciones de estado (§7.9.1)
    # ------------------------------------------------------------------
    def action_gt_compute(self):
        for run in self:
            if not run.slip_ids:
                raise UserError("No hay recibos en el período para calcular.")
            # También los 'En espera': los que crea "Generar recibos" nacen así y
            # deben recalcularse si se capturaron faltas/vacaciones después.
            # Red de seguridad: recibo GT sin estructura (saldría en 0).
            from ..hooks import gt_structure_types
            structure = self.env.ref(
                "l10n_gt_payroll.structure_gt_ordinaria", raise_if_not_found=False)
            types = gt_structure_types(self.env)
            sin_estructura = run.slip_ids.filtered(
                lambda s: s.state in ("draft", "verify") and not s.struct_id
                and s.contract_id.structure_type_id in types)
            if structure and sin_estructura:
                sin_estructura.write({"struct_id": structure.id})
            run.slip_ids.filtered(lambda s: s.state in ("draft", "verify")).compute_sheet()
            run.l10n_gt_state = "computed"

    def action_gt_confirm(self):
        for run in self:
            pendientes = run.slip_ids.filtered(lambda s: s.state == "draft")
            if pendientes:
                raise UserError(
                    "Existen recibos sin calcular; calcule la nómina antes de "
                    "confirmar (§7.1)."
                )
            run.slip_ids.filtered(lambda s: s.state in ("draft", "verify")).action_payslip_done()
            run.l10n_gt_state = "confirmed"
            # Estado estándar del lote en sintonía (la lista lo muestra).
            if run.state == "draft":
                run.state = "verify"

    def action_validate(self):
        """El 'Validar' / 'Crear asiento en borrador' estándar del lote (el de
        hr_payroll_account no se puede ocultar desde aquí) hace lo mismo que
        nuestro 'Confirmar': un solo flujo."""
        for run in self:
            if run.l10n_gt_state in ("draft", "computing"):
                run.action_gt_compute()
            if run.l10n_gt_state == "computed":
                run.action_gt_confirm()
        return True

    def action_gt_post(self):
        self.l10n_gt_state = "posted"

    def action_gt_close(self):
        """No permitir cerrar con cálculos pendientes (§3.2.3, §7.1)."""
        for run in self:
            pendientes = run.slip_ids.filtered(
                lambda s: s.state in ("draft", "verify")
            )
            if pendientes:
                raise UserError(
                    "No se puede cerrar el período: hay %d recibo(s) pendiente(s) "
                    "de cálculo o aprobación (§7.1)." % len(pendientes)
                )
            run.action_close() if hasattr(run, "action_close") else None
            run.l10n_gt_state = "closed"

    def action_gt_reopen(self):
        """Reabrir período (solo usuarios autorizados, §3.2.2)."""
        if not self.env.user.has_group("l10n_gt_payroll.group_payroll_manager"):
            raise UserError("Solo un responsable de nómina puede reabrir un período.")
        self.l10n_gt_state = "draft"
