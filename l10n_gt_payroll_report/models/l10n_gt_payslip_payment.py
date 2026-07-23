# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


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
    benefit_type = fields.Selection(
        selection=[
            ("salary", "Salario"),
            ("aguinaldo", "Aguinaldo"),
            ("bono14", "Bono 14"),
            ("vacaciones", "Vacaciones"),
            ("indemnizacion", "Indemnización"),
        ],
        string="Tipo", default="salary", required=True,
        help="Salario: cuenta contra el líquido del mes. Prestaciones (Aguinaldo, "
             "Bono 14, Vacaciones, Indemnización): drenan su pasivo acumulado sin "
             "afectar el líquido del salario.",
    )
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

    # --- Recálculo automático de quincenas al cambiar una recuperación ---
    def _l10n_gt_regen_if_recover(self):
        """Si cambió una línea de 'Recuperación de anticipo', regenera las líneas de
        salario pendientes para que las quincenas ya reflejen el descuento (sin tener
        que pulsar 'Generar programación'). No toca lo pagado."""
        if self.env.context.get("l10n_gt_skip_regen"):
            return
        payslips = self.filtered(
            lambda r: r.benefit_type == "anticipo_recover"
            and r.payslip_id and r.payslip_id.state == "draft"
        ).mapped("payslip_id")
        if payslips:
            payslips.with_context(
                l10n_gt_skip_regen=True).action_l10n_gt_generar_pagos()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._l10n_gt_regen_if_recover()
        return records

    # --- Inmutabilidad: un pago ya realizado no se puede modificar ni borrar ---
    _LOCKED_FIELDS = {"amount", "date", "name", "paid", "payslip_id", "benefit_type"}

    def write(self, vals):
        """Una vez marcado 'Pagado', el pago es histórico: solo se permite adjuntar
        el comprobante firmado o una observación, nunca cambiar monto/fecha/concepto
        ni revertir el pago. Así los ajustes por días recaen solo sobre lo pendiente
        y nunca descuadran lo ya entregado."""
        if self._LOCKED_FIELDS & set(vals):
            for rec in self:
                if rec.paid:
                    raise UserError(
                        "El pago «%s» ya está marcado como pagado y no se puede "
                        "modificar ni revertir. Registra un ajuste en una línea "
                        "pendiente. (Sí puedes adjuntar el comprobante firmado o "
                        "una observación.)" % (rec.name or "")
                    )
        res = super().write(vals)
        if {"amount", "benefit_type"} & set(vals):
            self._l10n_gt_regen_if_recover()
        return res

    def unlink(self):
        if any(rec.paid for rec in self):
            raise UserError(
                "No se puede eliminar un pago ya realizado. Lo pagado es histórico."
            )
        payslips = self.filtered(
            lambda r: r.benefit_type == "anticipo_recover"
            and r.payslip_id and r.payslip_id.state == "draft"
        ).mapped("payslip_id")
        res = super().unlink()
        if payslips and not self.env.context.get("l10n_gt_skip_regen"):
            payslips.with_context(
                l10n_gt_skip_regen=True).action_l10n_gt_generar_pagos()
        return res
