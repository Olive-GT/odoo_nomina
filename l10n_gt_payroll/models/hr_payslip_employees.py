# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import UserError


class HrPayslipEmployees(models.TransientModel):
    """'Generar recibos de nómina' del lote, para la nómina GT.

    La nómina GT no usa entradas de trabajo: el salario sale de los días
    calendario del contrato y las horas extra se capturan en el recibo. Pero el
    asistente estándar se detiene si hay entradas de trabajo encimadas (las crean,
    p. ej., las horas extra aprobadas de asistencia) y no genera ningún recibo.
    Para estructuras GT esa validación no bloquea (los conflictos se siguen
    marcando en Entradas de trabajo)."""

    _inherit = "hr.payslip.employees"

    def _l10n_gt_is_gt(self):
        structure = self.env.ref(
            "l10n_gt_payroll.structure_gt_ordinaria", raise_if_not_found=False)
        return bool(structure) and self.structure_id in (structure, self.env["hr.payroll.structure"])

    def compute_sheet(self):
        self.ensure_one()
        run = self.env["hr.payslip.run"].browse(self.env.context.get("active_id"))
        if run and self._l10n_gt_is_gt():
            run._l10n_gt_check_single_month()
            return super(HrPayslipEmployees, self.with_context(
                l10n_gt_skip_work_entry_check=True)).compute_sheet()
        return super().compute_sheet()


class HrWorkEntry(models.Model):
    _inherit = "hr.work.entry"

    def _check_if_error(self):
        res = super()._check_if_error()
        if self.env.context.get("l10n_gt_skip_work_entry_check"):
            return False
        return res
