# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

MANUAL_SUFFIX = " (ajuste manual)"


class L10nGtPayslipAdjustment(models.Model):
    """Ajuste manual de una línea del recibo.

    'Calcular hoja' borra y regenera todas las líneas, así que editar una línea
    directamente se pierde en el siguiente cálculo y, peor, deja el líquido y las
    deducciones desfasados. En su lugar, el ajuste se registra por concepto y se
    aplica DENTRO del motor de reglas (hr.salary.rule._compute_rule): el total
    manual reemplaza al calculado y todo lo que depende de él (GROSS, IGSS, NET,
    provisiones, póliza) sale consistente. Sobrevive a los recálculos y queda
    auditado (motivo + chatter)."""

    _name = "l10n.gt.payslip.adjustment"
    _description = "Ajuste manual de línea de nómina"
    _order = "id"

    payslip_id = fields.Many2one(
        "hr.payslip", string="Recibo", required=True, ondelete="cascade")
    struct_id = fields.Many2one(related="payslip_id.struct_id")
    company_id = fields.Many2one(related="payslip_id.company_id", store=True)
    currency_id = fields.Many2one(related="payslip_id.company_id.currency_id")
    salary_rule_id = fields.Many2one(
        "hr.salary.rule", string="Concepto", required=True, ondelete="restrict",
        help="Línea del recibo cuyo total se fija a mano.")
    code = fields.Char(related="salary_rule_id.code")
    computed_total = fields.Monetary(
        "Calculado", readonly=True,
        help="Total que la regla habría dado sin el ajuste (se actualiza al "
             "pulsar 'Calcular hoja').")
    total = fields.Monetary(
        "Total manual", required=True,
        help="Total de la línea tal como debe quedar en el recibo, con su signo: "
             "las deducciones van en negativo (p. ej. -150 para retener Q150 de "
             "ISR; +80 en ISR devolvería Q80). Al elegir el concepto se propone "
             "el total actual para que veas el signo.")
    note = fields.Char(
        "Motivo", required=True,
        help="Justificación del ajuste (queda en el historial del recibo).")

    _sql_constraints = [
        ("rule_uniq", "unique(payslip_id, salary_rule_id)",
         "Ya hay un ajuste manual para ese concepto en este recibo."),
    ]

    @api.onchange("salary_rule_id")
    def _onchange_salary_rule_id(self):
        """Propone el total actual de la línea (así se ve el signo que usa)."""
        if not self.salary_rule_id or self.total:
            return
        line = self.payslip_id.line_ids.filtered(
            lambda l: l.salary_rule_id == self.salary_rule_id)[:1]
        self.computed_total = line.total if line else 0.0
        self.total = line.total if line else 0.0

    # --- Solo en borrador / en espera, y con rastro en el chatter ---
    def _check_editable(self):
        if self.env.context.get("l10n_gt_adjustment_internal"):
            return
        for adj in self:
            if adj.payslip_id.state not in ("draft", "verify"):
                raise UserError(
                    "El recibo %s ya está confirmado: no se pueden cambiar sus "
                    "ajustes manuales." % (adj.payslip_id.name or ""))

    def _log(self, verb):
        if self.env.context.get("l10n_gt_adjustment_internal"):
            return
        for adj in self:
            adj.payslip_id.message_post(body=(
                "Ajuste manual %s: <b>%s</b> → %s %.2f (calculado %.2f). "
                "Motivo: %s" % (
                    verb, adj.salary_rule_id.name, adj.currency_id.symbol or "",
                    adj.total, adj.computed_total, adj.note or "")))

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._check_editable()
        recs._log("agregado")
        return recs

    def write(self, vals):
        self._check_editable()
        res = super().write(vals)
        if {"total", "note", "salary_rule_id"} & set(vals):
            self._log("modificado")
        return res

    def unlink(self):
        self._check_editable()
        self._log("eliminado")
        return super().unlink()


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    l10n_gt_adjustment_ids = fields.One2many(
        "l10n.gt.payslip.adjustment", "payslip_id", string="Ajustes manuales",
        copy=False,
        help="Conceptos cuyo total se fija a mano. Se aplican al pulsar "
             "'Calcular hoja' y sobreviven a los recálculos.")

    def _l10n_gt_manual_adjustment(self, rule):
        """Ajuste manual de este recibo para `rule` (recordset vacío si no hay)."""
        self.ensure_one()
        return self.l10n_gt_adjustment_ids.filtered(
            lambda a: a.salary_rule_id == rule)[:1]

    def compute_sheet(self):
        res = super().compute_sheet()
        # Marca visible en el recibo/boleta de las líneas fijadas a mano.
        for slip in self:
            adjusted = slip.l10n_gt_adjustment_ids.salary_rule_id
            if not adjusted:
                continue
            for line in slip.line_ids.filtered(
                    lambda l: l.salary_rule_id in adjusted
                    and not (l.name or "").endswith(MANUAL_SUFFIX)):
                line.name = (line.name or line.code or "") + MANUAL_SUFFIX
        return res
