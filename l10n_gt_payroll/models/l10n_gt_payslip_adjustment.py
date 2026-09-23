# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

MANUAL_SUFFIX = " (ajuste manual)"
DEFAULT_NOTE = "Editado en la tabla del recibo"
# Subtotales: su total sale de los conceptos que los componen; no se fijan a mano.
SUBTOTAL_CODES = ("GROSS", "NET")


class L10nGtPayslipAdjustment(models.Model):
    """Ajuste manual de una línea del recibo.

    El usuario edita el Total directamente en la tabla de 'Cálculo del salario';
    como 'Calcular hoja' borra y regenera todas las líneas, ese valor se guarda
    aquí, por concepto, y se aplica DENTRO del motor de reglas
    (hr.salary.rule._compute_rule): el total manual reemplaza al calculado y todo
    lo que depende de él (GROSS, IGSS, NET, provisiones, póliza) sale
    consistente. Sobrevive a los recálculos y queda auditado (chatter). Estos
    registros son el historial de ajustes: borrar uno devuelve el concepto a su
    valor calculado."""

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
        help="Línea del recibo cuyo total se fijó a mano.")
    code = fields.Char(related="salary_rule_id.code")
    computed_total = fields.Monetary(
        "Calculado", readonly=True,
        help="Total que la regla habría dado sin el ajuste (se actualiza al "
             "pulsar 'Calcular hoja').")
    total = fields.Monetary(
        "Total manual", required=True,
        help="Total de la línea tal como quedó en el recibo, con su signo (las "
             "deducciones en negativo).")
    note = fields.Char(
        "Motivo", default=DEFAULT_NOTE,
        help="Justificación del ajuste (queda en el historial del recibo).")

    _sql_constraints = [
        ("rule_uniq", "unique(payslip_id, salary_rule_id)",
         "Ya hay un ajuste manual para ese concepto en este recibo."),
    ]

    # --- Solo en borrador / en espera, y con rastro en el chatter ---
    def _check_editable(self):
        if self.env.context.get("l10n_gt_adjustment_internal"):
            return
        for adj in self:
            if adj.payslip_id.state not in ("draft", "verify"):
                raise UserError(
                    "El recibo %s ya está confirmado: no se pueden cambiar sus "
                    "ajustes manuales." % (adj.payslip_id.name or ""))
            if adj.salary_rule_id.code in SUBTOTAL_CODES:
                raise UserError(
                    "«%s» es un subtotal: ajusta los conceptos que lo componen."
                    % adj.salary_rule_id.name)

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
        help="Conceptos cuyo total se editó a mano en la tabla. Se aplican en cada "
             "'Calcular hoja'; borrar uno devuelve el concepto a su valor calculado.")

    def _l10n_gt_manual_adjustment(self, rule):
        """Ajuste manual de este recibo para `rule` (recordset vacío si no hay)."""
        self.ensure_one()
        return self.l10n_gt_adjustment_ids.filtered(
            lambda a: a.salary_rule_id == rule)[:1]

    def write(self, vals):
        """Edición del Total en la tabla de líneas → ajuste manual + recálculo.

        El formulario manda los cambios de las líneas como comandos (1, id, vals)
        en line_ids. 'Calcular hoja' no pasa por aquí (borra y crea las líneas
        directamente), así que estos comandos son siempre ediciones del usuario.
        El total editado no se escribe en la línea (se perdería en el siguiente
        cálculo): se guarda como ajuste del concepto y se recalcula la hoja, para
        que el líquido y las deducciones dependientes queden consistentes."""
        if self.env.context.get("l10n_gt_adjustment_internal"):
            return super().write(vals)
        if "line_ids" not in vals:
            res = super().write(vals)
            # Borrar un ajuste del historial devuelve el concepto a su valor
            # calculado: se recalcula en el acto.
            if any(isinstance(c, (list, tuple)) and c and c[0] in (2, 3)
                   for c in vals.get("l10n_gt_adjustment_ids") or []):
                self.filtered(lambda s: s.state in ("draft", "verify")).compute_sheet()
            return res
        edits = []  # (línea, total nuevo)
        commands = []
        Line = self.env["hr.payslip.line"]
        for cmd in vals["line_ids"]:
            if (isinstance(cmd, (list, tuple)) and len(cmd) == 3 and cmd[0] == 1
                    and isinstance(cmd[2], dict) and "total" in cmd[2]):
                line = Line.browse(cmd[1])
                line_vals = dict(cmd[2])
                new_total = line_vals.pop("total")
                if line.exists() and round(new_total - line.total, 2):
                    edits.append((line, new_total))
                if line_vals:
                    commands.append((1, cmd[1], line_vals))
                continue
            commands.append(cmd)
        if not edits:
            return super().write(vals)
        vals = dict(vals, line_ids=commands)
        res = super().write(vals)
        Adjustment = self.env["l10n.gt.payslip.adjustment"]
        slips = self.browse()
        for line, new_total in edits:
            slip = line.slip_id
            rule = line.salary_rule_id
            if not rule:
                continue
            adj = slip._l10n_gt_manual_adjustment(rule)
            computed = adj.computed_total if adj else line.total
            if adj and not round(new_total - adj.computed_total, 2):
                # Volvió a escribir el valor calculado: se quita el ajuste.
                adj.unlink()
            elif adj:
                adj.total = new_total
            else:
                Adjustment.create({
                    "payslip_id": slip.id,
                    "salary_rule_id": rule.id,
                    "total": new_total,
                    "computed_total": computed,
                })
            slips |= slip
        slips.compute_sheet()
        return res

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
