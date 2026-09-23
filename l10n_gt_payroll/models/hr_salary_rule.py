# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError


class HrSalaryRule(models.Model):
    """Marcas guatemaltecas para clasificar cada concepto (§4) y punto de entrada
    de los ajustes manuales del recibo (l10n.gt.payslip.adjustment)."""

    _inherit = "hr.salary.rule"

    l10n_gt_afecto_igss = fields.Boolean(
        "Afecto a IGSS",
        help="El concepto forma parte de la base de cálculo del IGSS "
             "(salario ordinario, horas extra, comisiones). §4.9.",
    )
    l10n_gt_afecto_isr = fields.Boolean(
        "Afecto a ISR",
        help="El concepto entra en la proyección de ISR asalariados. §4.10.",
    )
    l10n_gt_es_ordinario = fields.Boolean(
        "Forma parte del salario ordinario",
        help="Base para prestaciones (aguinaldo, bono 14, indemnización). §4.4.4.",
    )

    # ------------------------------------------------------------------
    # Ajustes manuales: se aplican DENTRO del motor de cálculo para que las
    # reglas dependientes (GROSS, IGSS, NET…) usen el total fijado a mano.
    # ------------------------------------------------------------------
    def _l10n_gt_adjustment(self, localdict):
        """Ajuste manual del recibo en cálculo para esta regla, o recordset vacío.
        En Odoo 18 `localdict['payslip']` es el propio registro hr.payslip."""
        slip = localdict.get("payslip")
        if (not isinstance(slip, models.Model) or slip._name != "hr.payslip"
                or len(slip) != 1 or not slip.id):
            return None
        return slip._l10n_gt_manual_adjustment(self) or None

    def _satisfy_condition(self, localdict):
        # Una línea fijada a mano aparece aunque su condición no se cumpla
        # (p. ej. retener ISR a quien la proyección no le calcula nada).
        if self._l10n_gt_adjustment(localdict):
            return True
        return super()._satisfy_condition(localdict)

    def _compute_rule(self, localdict):
        adj = self._l10n_gt_adjustment(localdict)
        if not adj:
            return super()._compute_rule(localdict)
        # Guarda lo que la regla habría dado, para auditoría/comparación.
        computed = 0.0
        if super()._satisfy_condition(localdict):
            try:
                amount, qty, rate = super()._compute_rule(localdict)
                computed = amount * qty * rate / 100.0
            except UserError:
                # La regla falla con estos datos; el ajuste manual la sustituye.
                computed = 0.0
        if adj.computed_total != computed:
            adj.with_context(l10n_gt_adjustment_internal=True).sudo().write(
                {"computed_total": computed})
        return adj.total, 1.0, 100.0
