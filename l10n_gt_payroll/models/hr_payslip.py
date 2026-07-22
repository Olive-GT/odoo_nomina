# -*- coding: utf-8 -*-
from odoo import models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def _l10n_gt_param(self, code):
        """Valor de un parámetro legal vigente a la fecha del recibo (§7.3).

        Reemplaza a payslip.rule_parameter(), inexistente en Odoo 18.
        """
        self.ensure_one()
        return self.env["hr.rule.parameter"]._get_parameter_from_code(
            code, self.date_to
        )

    def _l10n_gt_input(self, code):
        """Monto de una novedad (input) del recibo por código.

        En Odoo 18 el `inputs` del contexto de reglas es un dict; acceder por
        atributo (inputs.CODE) falla. Este helper lee las líneas directamente.
        """
        self.ensure_one()
        lines = self.input_line_ids.filtered(lambda l: l.code == code)
        return sum(lines.mapped("amount"))

    # ------------------------------------------------------------------
    # Días laborados y período (base calendario, §4.1.2)
    # ------------------------------------------------------------------
    def _l10n_gt_contracts_in_period(self):
        """Contratos del empleado que solapan el período del recibo."""
        self.ensure_one()
        return self.env["hr.contract"].search([
            ("employee_id", "=", self.employee_id.id),
            ("state", "in", ("open", "close")),
            ("date_start", "<=", self.date_to),
            "|", ("date_end", "=", False), ("date_end", ">=", self.date_from),
        ], order="date_start")

    def _l10n_gt_worked_days(self):
        """Días calendario laborados en el período (§4.1.2).

        En Guatemala la proporción del salario se calcula sobre días calendario
        (salario diario = mensual / 30), no sobre días hábiles. Para un mes
        completo devuelve los días del período (p.ej. 30).
        """
        self.ensure_one()
        contracts = self._l10n_gt_contracts_in_period()
        if not contracts:
            return (self.date_to - self.date_from).days + 1
        total = 0
        for c in contracts:
            ini = max(self.date_from, c.date_start)
            fin = min(self.date_to, c.date_end or self.date_to)
            dias = (fin - ini).days + 1
            if dias > 0:
                total += dias
        return total

    def _l10n_gt_is_full_period(self):
        """True si la relación laboral cubre todo el período (§4.1.2).

        Se basa en la cobertura del contrato, no en días hábiles: un empleado
        activo todo el mes recibe el salario completo aunque el mes tenga fines
        de semana o asuetos.
        """
        self.ensure_one()
        contracts = self._l10n_gt_contracts_in_period()
        if not contracts:
            return bool(self.contract_id)
        starts_covered = min(contracts.mapped("date_start")) <= self.date_from
        ends = [c.date_end or self.date_to for c in contracts]
        ends_covered = max(ends) >= self.date_to
        return starts_covered and ends_covered

    # ------------------------------------------------------------------
    # Salario ordinario con tramos de contrato (§4.1.4)
    # ------------------------------------------------------------------
    def _l10n_gt_ordinary_salary(self):
        """Salario ordinario del período considerando cambios salariales.

        - Un único contrato que cubre todo el período: salario completo.
        - Ingreso/egreso a mitad del período: proporcional por días calendario
          (salario diario = wage / 30).
        - Cambio de salario en el período: proporcional por tramos.
        """
        self.ensure_one()
        contracts = self._l10n_gt_contracts_in_period()
        if not contracts:
            return self.contract_id.wage if self.contract_id else 0.0

        if len(contracts) == 1 and self._l10n_gt_is_full_period():
            return contracts.wage

        total = 0.0
        for c in contracts:
            ini = max(self.date_from, c.date_start)
            fin = min(self.date_to, c.date_end or self.date_to)
            dias = (fin - ini).days + 1
            if dias <= 0:
                continue
            total += (c.wage / 30.0) * dias
        return total
