# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrContract(models.Model):
    """El contrato es el centro de administración de la nómina: desde aquí se ven
    todos los periodos (nóminas mensuales), cuánto se ha pagado y cuánto falta."""

    _inherit = "hr.contract"

    l10n_gt_payslip_count = fields.Integer(
        "Periodos", compute="_compute_l10n_gt_payslip_stats")
    l10n_gt_pending_total = fields.Monetary(
        "Pendiente total", compute="_compute_l10n_gt_payslip_stats",
        currency_field="currency_id")

    def _l10n_gt_money(self, amount):
        """Formatea un monto (símbolo al inicio + separador de miles) para el
        estado de cuenta consolidado."""
        self.ensure_one()
        symbol = (self.company_id.currency_id.symbol or "Q")
        return "%s%s" % (symbol, "{:,.2f}".format(amount or 0.0))

    def _l10n_gt_payslips(self):
        self.ensure_one()
        return self.env["hr.payslip"].search([
            ("contract_id", "=", self.id),
            ("state", "!=", "cancel"),
        ], order="date_from desc")

    @api.depends("employee_id")
    def _compute_l10n_gt_payslip_stats(self):
        for contract in self:
            slips = contract._l10n_gt_payslips() if contract.id else \
                self.env["hr.payslip"]
            contract.l10n_gt_payslip_count = len(slips)
            contract.l10n_gt_pending_total = sum(
                slips.mapped("l10n_gt_pending_amount"))

    def action_l10n_gt_view_payslips(self):
        """Abre la lista de periodos (nóminas) de este contrato."""
        self.ensure_one()
        list_view = self.env.ref(
            "l10n_gt_payroll_report.view_payslip_list_gt_periodos")
        return {
            "type": "ir.actions.act_window",
            "name": "Periodos / Nóminas",
            "res_model": "hr.payslip",
            "view_mode": "list,form",
            "views": [(list_view.id, "list"), (False, "form")],
            "domain": [("contract_id", "=", self.id)],
            "context": {
                "default_contract_id": self.id,
                "default_employee_id": self.employee_id.id,
            },
        }

    def action_l10n_gt_estado_cuenta(self):
        """Imprime el estado de cuenta consolidado (todos los periodos)."""
        self.ensure_one()
        return self.env.ref(
            "l10n_gt_payroll_report.action_report_estado_cuenta_contrato"
        ).report_action(self)
