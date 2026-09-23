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

    # ------------------------------------------------------------------
    # Edición en la tabla de 'Cálculo del salario'
    # ------------------------------------------------------------------
    def _l10n_gt_line_sources(self):
        """Conceptos cuyo valor sale de un DATO del recibo, no de un ajuste.

        Editar/agregar/quitar su línea en la tabla escribe ese dato (y la regla lo
        recalcula), en vez de fijar un total manual:
        - by='qty': la Cantidad de la línea es el dato (horas extra → horas).
        - by='total': el Total es el dato (monto de la entrada, con `sign`).
        kind='input' → hr.payslip.input de ese código; kind='field' → campo del
        recibo. Otros módulos extienden este mapa (p. ej. VAC → días pagados)."""
        return {
            "HEXTD": {"kind": "input", "target": "HE_DIURNA", "by": "qty", "sign": 1},
            "HEXTN": {"kind": "input", "target": "HE_NOCTURNA", "by": "qty", "sign": 1},
            "COMIS": {"kind": "input", "target": "COMIS", "by": "total", "sign": 1},
            "BONIF": {"kind": "input", "target": "BONIF", "by": "total", "sign": 1},
            "OTRDED": {"kind": "input", "target": "OTRDED", "by": "total", "sign": -1},
        }

    def _l10n_gt_set_source(self, src, value):
        """Escribe el dato de un concepto (entrada o campo del recibo)."""
        self.ensure_one()
        if src["kind"] == "field":
            self.with_context(l10n_gt_adjustment_internal=True).write(
                {src["target"]: value})
            return
        inputs = self.input_line_ids.filtered(lambda i: i.code == src["target"])
        if not value:
            inputs.unlink()
        elif inputs:
            inputs[0].amount = value
            inputs[1:].unlink()
        else:
            itype = self.env["hr.payslip.input.type"].search(
                [("code", "=", src["target"])], limit=1)
            if not itype:
                raise UserError("No existe el tipo de entrada %s." % src["target"])
            self.env["hr.payslip.input"].create({
                "payslip_id": self.id, "input_type_id": itype.id, "amount": value})

    def _l10n_gt_set_adjustment(self, rule, total, computed):
        """Crea/actualiza el ajuste manual de `rule`; lo quita si `total` vuelve
        a ser el valor calculado."""
        self.ensure_one()
        adj = self._l10n_gt_manual_adjustment(rule)
        if adj and not round(total - adj.computed_total, 2):
            adj.unlink()
        elif adj:
            adj.total = total
        else:
            self.env["l10n.gt.payslip.adjustment"].create({
                "payslip_id": self.id, "salary_rule_id": rule.id,
                "total": total, "computed_total": computed})

    def _l10n_gt_apply_line_edit(self, action, rule, qty=None, total=None, line=None):
        """Aplica una acción de la tabla sobre un concepto:
        'qty'/'total' (editar la columna), 'add' (fila nueva), 'delete' (quitar)."""
        self.ensure_one()
        if self.state not in ("draft", "verify"):
            raise UserError("El recibo ya está confirmado: no se puede modificar.")
        if rule.code in SUBTOTAL_CODES:
            raise UserError("«%s» es un subtotal: ajusta los conceptos que lo "
                            "componen." % rule.name)
        src = self._l10n_gt_line_sources().get(rule.code)
        adj = self._l10n_gt_manual_adjustment(rule)
        computed = line.total if line else 0.0
        if action == "delete":
            if src:
                self._l10n_gt_set_source(src, 0.0)
                adj.unlink()
            else:
                self._l10n_gt_set_adjustment(rule, 0.0, computed)
        elif action == "qty":
            if src and src["by"] == "qty":
                self._l10n_gt_set_source(src, qty)
                adj.unlink()
        elif action == "add" and src and src["by"] == "qty":
            self._l10n_gt_set_source(src, qty)
            adj.unlink()
        elif src and src["by"] == "total":  # 'total' o 'add'
            self._l10n_gt_set_source(src, src["sign"] * total)
            adj.unlink()
        else:  # 'total' o 'add' de un concepto calculado → ajuste manual
            self._l10n_gt_set_adjustment(rule, total, computed)

    def write(self, vals):
        """La tabla de 'Cálculo del salario' como único lugar de captura.

        El formulario manda las ediciones de la tabla como comandos en line_ids:
        (1, id, vals) editar, (0, 0, vals) fila nueva, (2, id) quitar. 'Calcular
        hoja' no pasa por aquí (borra y crea las líneas directamente), así que
        estos comandos son siempre acciones del usuario. No se escriben en las
        líneas (se perderían en el siguiente cálculo): se traducen al dato del
        concepto (horas, monto de entrada) o a un ajuste manual, y se recalcula la
        hoja para que el líquido y todo lo dependiente quede consistente."""
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
        Line = self.env["hr.payslip.line"]
        Rule = self.env["hr.salary.rule"]
        ops = []  # (recibo, acción, regla, kwargs)
        commands = []
        for cmd in vals["line_ids"]:
            if not isinstance(cmd, (list, tuple)) or not cmd:
                commands.append(cmd)
                continue
            if cmd[0] == 1 and len(cmd) == 3 and isinstance(cmd[2], dict):
                line = Line.browse(cmd[1]).exists()
                line_vals = dict(cmd[2])
                qty = line_vals.pop("quantity", None)
                total = line_vals.pop("total", None)
                if line and line.salary_rule_id:
                    if qty is not None and round(qty - line.quantity, 4):
                        ops.append((line.slip_id, "qty", line.salary_rule_id,
                                    {"qty": qty, "line": line}))
                    elif total is not None and round(total - line.total, 2):
                        ops.append((line.slip_id, "total", line.salary_rule_id,
                                    {"total": total, "line": line}))
                if line_vals:
                    commands.append((1, cmd[1], line_vals))
                continue
            if cmd[0] == 0 and len(cmd) == 3 and isinstance(cmd[2], dict):
                rule = Rule.browse(cmd[2].get("salary_rule_id") or 0).exists()
                if rule and len(self) == 1:
                    ops.append((self, "add", rule, {
                        "qty": cmd[2].get("quantity", 1.0),
                        "total": cmd[2].get("total") or 0.0}))
                continue
            if cmd[0] == 2:
                line = Line.browse(cmd[1]).exists()
                if line and line.salary_rule_id:
                    ops.append((line.slip_id, "delete", line.salary_rule_id,
                                {"line": line}))
                continue
            commands.append(cmd)
        if not ops:
            return super().write(vals)
        res = super().write(dict(vals, line_ids=commands))
        slips = self.browse()
        for slip, action, rule, kw in ops:
            slip._l10n_gt_apply_line_edit(action, rule, **kw)
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
