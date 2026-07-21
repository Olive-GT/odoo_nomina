# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import fields, models
from odoo.exceptions import UserError


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    l10n_gt_move_id = fields.Many2one("account.move", string="Asiento de nómina",
                                      copy=False)

    def _l10n_gt_poliza_data(self):
        """Agrega débitos/créditos por cuenta contable a partir de los recibos.

        Independiente de la contabilidad: sirve para el reporte de póliza (§6.9)
        aunque el cliente no genere el asiento en Odoo.
        """
        self.ensure_one()
        acc = defaultdict(lambda: {"debit": 0.0, "credit": 0.0, "name": ""})
        for slip in self.slip_ids:
            for line in slip.line_ids:
                rule = line.salary_rule_id
                total = line.total
                if not total:
                    continue
                debit_acc = rule.l10n_gt_account_debit_id
                credit_acc = rule.l10n_gt_account_credit_id
                if debit_acc:
                    key = debit_acc.id
                    acc[key]["name"] = debit_acc.display_name
                    if total >= 0:
                        acc[key]["debit"] += total
                    else:
                        acc[key]["credit"] += -total
                if credit_acc:
                    key = credit_acc.id
                    acc[key]["name"] = credit_acc.display_name
                    if total >= 0:
                        acc[key]["credit"] += total
                    else:
                        acc[key]["debit"] += -total
        rows = [
            {"account_id": k, "name": v["name"],
             "debit": round(v["debit"], 2), "credit": round(v["credit"], 2)}
            for k, v in acc.items()
        ]
        return sorted(rows, key=lambda r: r["name"])

    def action_gt_generate_move(self):
        """Genera el asiento contable de la nómina (§2.9)."""
        self.ensure_one()
        rows = self._l10n_gt_poliza_data()
        if not rows:
            raise UserError(
                "No hay cuentas contables configuradas en los conceptos de "
                "nómina. Configure las cuentas débito/crédito en las reglas "
                "salariales."
            )
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
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": move.id,
            "view_mode": "form",
        }
