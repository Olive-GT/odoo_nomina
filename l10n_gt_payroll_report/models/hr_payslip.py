# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields, models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    # Frecuencia heredada del contrato (define el desglose de comprobantes).
    l10n_gt_payment_frequency = fields.Selection(
        related="contract_id.l10n_gt_payment_frequency",
        string="Frecuencia de pago", readonly=True,
    )

    # Comprobantes de pago firmados (se imprimen, se firman y se suben de vuelta
    # para resguardo). El recibo/cálculo sigue siendo mensual.
    l10n_gt_signed_month = fields.Binary("Boleta mensual firmada", attachment=True)
    l10n_gt_signed_month_name = fields.Char("Archivo boleta mensual")
    l10n_gt_signed_q1 = fields.Binary("Comprobante 1ª quincena firmado", attachment=True)
    l10n_gt_signed_q1_name = fields.Char("Archivo 1ª quincena")
    l10n_gt_signed_q2 = fields.Binary("Comprobante 2ª quincena firmado", attachment=True)
    l10n_gt_signed_q2_name = fields.Char("Archivo 2ª quincena")
    l10n_gt_signed_w1 = fields.Binary("Comprobante semana 1 firmado", attachment=True)
    l10n_gt_signed_w1_name = fields.Char("Archivo semana 1")
    l10n_gt_signed_w2 = fields.Binary("Comprobante semana 2 firmado", attachment=True)
    l10n_gt_signed_w2_name = fields.Char("Archivo semana 2")
    l10n_gt_signed_w3 = fields.Binary("Comprobante semana 3 firmado", attachment=True)
    l10n_gt_signed_w3_name = fields.Char("Archivo semana 3")
    l10n_gt_signed_w4 = fields.Binary("Comprobante semana 4 firmado", attachment=True)
    l10n_gt_signed_w4_name = fields.Char("Archivo semana 4")

    l10n_gt_first_quincena_amount = fields.Monetary(
        "Anticipo 1ª quincena (opcional)",
        help="Este recibo es del MES completo. Este campo es opcional: sirve solo "
             "para fijar manualmente cuánto se paga en el PRIMER pago (a mitad de "
             "mes) de este mes en particular. El segundo pago (fin de mes) será el "
             "líquido del mes menos este monto. Déjalo vacío (0) para que el sistema "
             "use el monto fijo del contrato o el método de la empresa (mitades "
             "iguales por defecto). No indica que el recibo sea de una quincena: el "
             "recibo siempre es mensual y de él imprimes los dos comprobantes.",
    )

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
        """Monto a pagar en la quincena n.

        Prioridad:
        1. Monto fijo de primera quincena definido en el contrato (anticipo real).
           La 2ª quincena = líquido del mes − 1ª, para que la boleta coincida
           exactamente con lo pagado (sin discrepancias).
        2. Si no hay monto fijo, se usa el método de la empresa:
           - ordinary_half: 1ª = salario ordinario / 2 (anticipo); 2ª = resto.
           - net_half: mitades iguales del líquido (anexo 8.1/8.2).
        """
        self.ensure_one()
        net = self._l10n_gt_line("NET")
        # Prioridad: monto manual del recibo > monto del contrato > método empresa
        fixed = self.l10n_gt_first_quincena_amount
        if not fixed and self.contract_id:
            fixed = self.contract_id.l10n_gt_first_quincena_amount
        if fixed and fixed > 0:
            first = round(min(fixed, net), 2)
        else:
            method = self.company_id.l10n_gt_quincena_method or "ordinary_half"
            if method == "net_half":
                first = round(net / 2.0, 2)
            else:  # ordinary_half
                first = round(self._l10n_gt_line("SALORD") / 2.0, 2)
        return first if n == 1 else round(net - first, 2)

    def _l10n_gt_semana_dates(self, n):
        """Fechas de la semana n (1-4) del período mensual (semanas de 7 días,
        la 4ª toma hasta el fin de mes)."""
        self.ensure_one()
        ini = self.date_from + timedelta(days=(n - 1) * 7)
        if n >= 4:
            fin = self.date_to
        else:
            fin = self.date_from + timedelta(days=n * 7 - 1)
        return ini, min(fin, self.date_to)

    def _l10n_gt_semana_amount(self, n):
        """Monto a pagar en la semana n: líquido del mes en 4 partes (la 4ª es
        el saldo, para que sumen exacto)."""
        self.ensure_one()
        net = self._l10n_gt_line("NET")
        base = round(net / 4.0, 2)
        if n >= 4:
            return round(net - base * 3, 2)
        return base

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
