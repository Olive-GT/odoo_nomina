# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import fields, models
from odoo.exceptions import UserError


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    l10n_gt_move_id = fields.Many2one("account.move", string="Asiento de nómina",
                                      copy=False)

    def _l10n_gt_poliza_data(self):
        """Agrega la póliza por cuenta contable a partir de los recibos
        CONFIRMADOS del lote (§6.9, §2.9).

        Cada concepto de nómina con cuenta débito Y crédito se contabiliza como
        un par balanceado por su monto absoluto: DEBE a la cuenta débito, HABER
        a la cuenta crédito. Así las retenciones (IGSS/ISR, con total negativo)
        se registran en el sentido correcto y el asiento SIEMPRE cuadra.

        Devuelve una fila por cuenta con el saldo neto (un solo lado). Sirve para
        el reporte de póliza aunque el cliente no genere el asiento en Odoo.
        """
        self.ensure_one()
        acc = defaultdict(lambda: {"debit": 0.0, "credit": 0.0, "name": ""})
        for slip in self.slip_ids.filtered(lambda s: s.state in ("done", "paid")):
            for line in slip.line_ids:
                rule = line.salary_rule_id
                amount = abs(line.total)
                debit_acc = rule.l10n_gt_account_debit_id
                credit_acc = rule.l10n_gt_account_credit_id
                # Solo conceptos con AMBAS cuentas (par balanceado). Los
                # subtotales (GROSS/NET/TOTAL) no llevan cuentas y se ignoran.
                if not amount or not (debit_acc and credit_acc):
                    continue
                acc[debit_acc.id]["name"] = debit_acc.display_name
                acc[debit_acc.id]["debit"] += amount
                acc[credit_acc.id]["name"] = credit_acc.display_name
                acc[credit_acc.id]["credit"] += amount
        rows = []
        for k, v in acc.items():
            bal = round(v["debit"] - v["credit"], 2)
            if not bal:
                continue
            rows.append({
                "account_id": k,
                "name": v["name"],
                "debit": bal if bal > 0 else 0.0,
                "credit": -bal if bal < 0 else 0.0,
            })
        # Débitos primero, luego créditos; alfabético dentro de cada bloque.
        return sorted(rows, key=lambda r: (r["credit"] > 0, r["name"]))

    def action_gt_generate_move(self):
        """Genera el asiento contable (en borrador) de la nómina del lote (§2.9).
        Queda en borrador para revisión; el usuario lo contabiliza (Publicar)."""
        self.ensure_one()
        if self.l10n_gt_move_id:
            raise UserError(
                "Ya existe un asiento (%s) para esta nómina. Elimínelo si desea "
                "regenerarlo." % self.l10n_gt_move_id.name)
        rows = self._l10n_gt_poliza_data()
        if not rows:
            raise UserError(
                "No hay conceptos con cuentas contables configuradas en recibos "
                "confirmados. Configure las cuentas débito y crédito en las "
                "reglas salariales (pestaña 'Contabilidad GT') y confirme los "
                "recibos del lote.")
        total_d = round(sum(r["debit"] for r in rows), 2)
        total_c = round(sum(r["credit"] for r in rows), 2)
        if total_d != total_c:
            raise UserError(
                "El asiento no cuadra: débitos Q%.2f ≠ créditos Q%.2f. Verifique "
                "que cada concepto tenga cuenta débito Y crédito." % (total_d, total_c))
        journal = self.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", self.company_id.id)],
            limit=1)
        if not journal:
            raise UserError("No se encontró un diario contable general.")
        move_lines = [(0, 0, {
            "account_id": r["account_id"],
            "name": self.name,
            "debit": r["debit"],
            "credit": r["credit"],
        }) for r in rows]
        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": journal.id,
            "date": self.date_end,
            "ref": "Nómina %s" % self.name,
            "line_ids": move_lines,
        })
        self.l10n_gt_move_id = move.id
        return self.action_gt_view_move()

    def action_gt_view_move(self):
        """Abre el asiento contable generado."""
        self.ensure_one()
        if not self.l10n_gt_move_id:
            raise UserError("Esta nómina aún no tiene asiento contable.")
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.l10n_gt_move_id.id,
            "view_mode": "form",
            "name": "Asiento de nómina",
        }
