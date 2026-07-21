# -*- coding: utf-8 -*-
from odoo import fields, models


class HrSalaryRule(models.Model):
    """Cuentas contables por concepto (§7.3)."""

    _inherit = "hr.salary.rule"

    l10n_gt_account_debit_id = fields.Many2one(
        "account.account", string="Cuenta débito",
        company_dependent=True, ondelete="restrict",
    )
    l10n_gt_account_credit_id = fields.Many2one(
        "account.account", string="Cuenta crédito",
        company_dependent=True, ondelete="restrict",
    )
