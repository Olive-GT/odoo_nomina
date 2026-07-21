# -*- coding: utf-8 -*-
from odoo import fields, models


class L10nGtIsrDeduction(models.Model):
    """Deducciones personales comprobables autorizadas (§4.10.4).

    Donaciones comprobables, primas de seguro de vida no reembolsables, etc.
    El usuario adjunta la constancia correspondiente.
    """

    _name = "l10n.gt.isr.deduction"
    _description = "Deducción comprobable de ISR"
    _order = "year desc, employee_id"

    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")
    year = fields.Integer(required=True)
    deduction_type = fields.Selection(
        selection=[
            ("donation", "Donación comprobable"),
            ("life_insurance", "Prima seguro de vida no reembolsable"),
            ("invoice", "Facturas (IVA/gastos autorizados)"),
            ("other", "Otra"),
        ],
        string="Tipo",
        required=True,
        default="invoice",
    )
    amount = fields.Monetary("Monto", required=True)
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda s: s.env.ref("base.GTQ", raise_if_not_found=False),
    )
    description = fields.Char("Descripción / constancia")
    attachment_ids = fields.Many2many("ir.attachment", string="Constancias")
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company
    )
