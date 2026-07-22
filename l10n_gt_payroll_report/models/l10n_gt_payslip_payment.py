# -*- coding: utf-8 -*-
from odoo import api, fields, models


class L10nGtPayslipPayment(models.Model):
    """Estado de cuenta de la nómina: cada línea es un pago (real o programado)
    hecho al trabajador dentro del mes calculado.

    El líquido del mes es la deuda total; los pagos la van saldando. Si se
    reducen días (faltas) el líquido baja y, como el saldo pendiente = líquido −
    pagado, la reducción recae SIEMPRE sobre lo aún no pagado. Así nunca se
    descuadra lo ya entregado al trabajador.
    """

    _name = "l10n.gt.payslip.payment"
    _description = "Pago de nómina (estado de cuenta)"
    _order = "date, id"

    payslip_id = fields.Many2one(
        "hr.payslip", string="Recibo", required=True, ondelete="cascade")
    company_id = fields.Many2one(
        related="payslip_id.company_id", store=True)
    currency_id = fields.Many2one(
        related="payslip_id.company_id.currency_id", store=True)
    date = fields.Date(
        "Fecha de pago", required=True, default=fields.Date.context_today)
    name = fields.Char("Concepto", required=True, default="Pago")
    amount = fields.Monetary("Monto", required=True)
    paid = fields.Boolean(
        "Pagado", default=False,
        help="Marca la línea cuando el pago ya se entregó al trabajador. El saldo "
             "pendiente se calcula solo con las líneas pagadas, de modo que una "
             "reducción posterior de días recae únicamente sobre lo no pagado.")
    reference = fields.Char("Referencia / observación")
    signed_doc = fields.Binary("Comprobante firmado", attachment=True)
    signed_doc_name = fields.Char("Archivo")

    @api.depends("name", "amount")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s — %.2f" % (rec.name or "Pago", rec.amount or 0.0)
