# -*- coding: utf-8 -*-
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
    # Transiciones de estado (§7.9.1)
    # ------------------------------------------------------------------
    def action_gt_compute(self):
        for run in self:
            if not run.slip_ids:
                raise UserError("No hay recibos en el período para calcular.")
            run.slip_ids.filtered(lambda s: s.state == "draft").compute_sheet()
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
