# -*- coding: utf-8 -*-
from datetime import timedelta

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

    # ------------------------------------------------------------------
    # Días trabajados
    # ------------------------------------------------------------------
    def _l10n_gt_worked_days(self):
        """Días efectivamente pagados en el período (§4.1.2).

        Suma los días de las entradas de trabajo que cuentan como pagadas.
        Si no hay work entries (configuración mínima), asume período completo (30).
        """
        self.ensure_one()
        paid = sum(
            wd.number_of_days
            for wd in self.worked_days_line_ids
            if wd.work_entry_type_id and not wd.work_entry_type_id.is_leave
        )
        return paid or 30.0

    def _l10n_gt_is_full_period(self):
        """True si el empleado laboró el período completo (§4.1.2)."""
        self.ensure_one()
        return self._l10n_gt_worked_days() >= 30.0

    # ------------------------------------------------------------------
    # Salario ordinario con tramos de contrato (§4.1.4)
    # ------------------------------------------------------------------
    def _l10n_gt_ordinary_salary(self):
        """Salario ordinario del período considerando cambios salariales.

        Recorre los contratos del empleado que solapan el período y prorratea
        cada tramo por sus días de vigencia (salario diario = wage / 30).
        Si un único contrato cubre todo el período, devuelve el salario completo.
        """
        self.ensure_one()
        date_from, date_to = self.date_from, self.date_to

        contracts = self.env["hr.contract"].search([
            ("employee_id", "=", self.employee_id.id),
            ("state", "in", ("open", "close")),
            ("date_start", "<=", date_to),
            "|", ("date_end", "=", False), ("date_end", ">=", date_from),
        ], order="date_start")

        # Sin historial de tramos: cálculo simple sobre el contrato del recibo.
        if len(contracts) <= 1:
            contract = self.contract_id or contracts[:1]
            if not contract:
                return 0.0
            if self._l10n_gt_is_full_period():
                return contract.wage
            return (contract.wage / 30.0) * self._l10n_gt_worked_days()

        # Con tramos: suma proporcional por días de vigencia de cada contrato.
        total = 0.0
        for contract in contracts:
            tramo_ini = max(date_from, contract.date_start)
            tramo_fin = min(date_to, contract.date_end or date_to)
            dias = (tramo_fin - tramo_ini).days + 1
            if dias <= 0:
                continue
            total += (contract.wage / 30.0) * dias
        return total
