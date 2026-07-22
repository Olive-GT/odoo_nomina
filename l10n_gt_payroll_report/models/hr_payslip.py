# -*- coding: utf-8 -*-
from odoo import models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def _l10n_gt_line(self, code):
        """Total de una línea por código (positivo). 0 si no existe."""
        self.ensure_one()
        line = self.line_ids.filtered(lambda l: l.code == code)
        return line.total if line else 0.0

    def _l10n_gt_quincena_dates(self, n):
        """Fechas de la 1ª (1-15) o 2ª (16-fin) quincena del período."""
        self.ensure_one()
        df = self.date_from
        if n == 1:
            return df, df.replace(day=15)
        return df.replace(day=16), self.date_to

    def _l10n_gt_quincena_amount(self, n):
        """Monto a pagar en la quincena n, según el método de la empresa.

        - ordinary_half: la 1ª quincena es un anticipo del salario ordinario
          (ordinario/2) y la 2ª liquida el resto del líquido del mes (incluye la
          bonificación y todas las deducciones). La 2ª suele ser mayor.
        - net_half: cada quincena paga la mitad del líquido del mes (como en el
          anexo 8.1/8.2 del diseño funcional).
        """
        self.ensure_one()
        net = self._l10n_gt_line("NET")
        method = self.company_id.l10n_gt_quincena_method or "ordinary_half"
        if method == "net_half":
            first = round(net / 2.0, 2)
        else:  # ordinary_half
            first = round(self._l10n_gt_line("SALORD") / 2.0, 2)
        return first if n == 1 else round(net - first, 2)

    def _l10n_gt_lines_by_category(self, category_code, sign="all"):
        """Suma de líneas por categoría; sign='in' positivas, 'out' negativas."""
        self.ensure_one()
        lines = self.line_ids.filtered(
            lambda l: l.category_id.code == category_code
        )
        if sign == "in":
            return sum(l.total for l in lines if l.total > 0)
        if sign == "out":
            return sum(-l.total for l in lines if l.total < 0)
        return sum(lines.mapped("total"))
