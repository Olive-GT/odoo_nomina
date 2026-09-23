# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .l10n_gt_payslip_adjustment import SUBTOTAL_CODES


class HrPayslipLine(models.Model):
    """Soporte de la edición en la tabla de 'Cálculo del salario': qué columnas
    puede tocar el usuario en cada fila y el llenado de una fila nueva."""

    _inherit = "hr.payslip.line"

    l10n_gt_qty_editable = fields.Boolean(
        compute="_compute_l10n_gt_editable",
        help="La Cantidad de esta línea es un dato de entrada (horas extra, días "
             "de vacaciones pagadas) y se captura en la tabla.")
    l10n_gt_total_editable = fields.Boolean(compute="_compute_l10n_gt_editable")
    l10n_gt_is_adjusted = fields.Boolean(
        compute="_compute_l10n_gt_editable",
        help="El total de esta línea está fijado a mano (ajuste manual).")

    @api.depends("salary_rule_id", "slip_id")
    def _compute_l10n_gt_editable(self):
        for line in self:
            code = line.salary_rule_id.code
            src = line.slip_id._l10n_gt_line_sources().get(code) if code else None
            line.l10n_gt_qty_editable = bool(src and src["by"] == "qty")
            line.l10n_gt_total_editable = code not in SUBTOTAL_CODES
            line.l10n_gt_is_adjusted = bool(
                code and line.slip_id.l10n_gt_adjustment_ids.filtered(
                    lambda a: a.salary_rule_id == line.salary_rule_id))

    @api.onchange("salary_rule_id")
    def _onchange_l10n_gt_salary_rule_id(self):
        """Fila nueva en la tabla: toma nombre y orden del concepto elegido."""
        if self.salary_rule_id and not self._origin.id:
            self.name = self.salary_rule_id.name
            self.sequence = self.salary_rule_id.sequence
            self.quantity = 1.0
            self.rate = 100.0
