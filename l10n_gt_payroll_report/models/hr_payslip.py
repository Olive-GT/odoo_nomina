# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    # Desglose de comprobantes: se hereda del contrato (campo propio, distinto de
    # 'Programar pago' que es el período del salario). Mensual->1, Quincenal->2,
    # Semanal->4. El cálculo siempre es mensual.
    l10n_gt_payment_frequency = fields.Selection(
        related="contract_id.l10n_gt_payment_frequency",
        string="Frecuencia de pago (comprobantes)", store=True, readonly=True,
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
        help="Solo con método 'Manual': cuánto se paga en el PRIMER pago (a mitad de "
             "mes) de este mes en particular. El segundo pago (fin de mes) será el "
             "líquido del mes menos este monto. Si se deja vacío, se usa el monto fijo "
             "del contrato. El recibo siempre es mensual y de él imprimes los dos "
             "comprobantes.",
    )

    # Método de reparto en dos quincenas. Se hereda del contrato (por empleado) y
    # puede ajustarse en este recibo. No cambia el cálculo mensual, solo cómo se
    # divide el líquido en los comprobantes.
    l10n_gt_quincena_method = fields.Selection(
        selection=[
            ("net_half", "Mitades iguales (líquido ÷ 2)"),
            ("ordinary_half", "Anticipo del ordinario (1ª = ordinario ÷ 2; 2ª el resto)"),
            ("manual", "Manual (defino el monto de la 1ª quincena)"),
        ],
        string="Método de reparto de quincenas",
        compute="_compute_l10n_gt_quincena_method",
        store=True, readonly=False,
        help="Cómo se divide el líquido del mes en las dos quincenas. Se hereda del "
             "contrato; puedes cambiarlo solo para este recibo.",
    )

    # Montos calculados de cada comprobante (solo visualización, no se almacenan).
    l10n_gt_amount_q1 = fields.Monetary(
        "Pago 1ª quincena", compute="_compute_l10n_gt_split")
    l10n_gt_amount_q2 = fields.Monetary(
        "Pago 2ª quincena", compute="_compute_l10n_gt_split")
    l10n_gt_amount_w1 = fields.Monetary(
        "Pago semana 1", compute="_compute_l10n_gt_split")
    l10n_gt_amount_w2 = fields.Monetary(
        "Pago semana 2", compute="_compute_l10n_gt_split")
    l10n_gt_amount_w3 = fields.Monetary(
        "Pago semana 3", compute="_compute_l10n_gt_split")
    l10n_gt_amount_w4 = fields.Monetary(
        "Pago semana 4", compute="_compute_l10n_gt_split")

    @api.depends("contract_id")
    def _compute_l10n_gt_quincena_method(self):
        for slip in self:
            slip.l10n_gt_quincena_method = (
                slip.contract_id.l10n_gt_quincena_method
                or slip.company_id.l10n_gt_quincena_method or "net_half"
            )

    @api.depends(
        "line_ids.total", "line_ids.code", "l10n_gt_quincena_method",
        "l10n_gt_first_quincena_amount", "contract_id.l10n_gt_first_quincena_amount",
    )
    def _compute_l10n_gt_split(self):
        for slip in self:
            slip.l10n_gt_amount_q1 = slip._l10n_gt_quincena_amount(1)
            slip.l10n_gt_amount_q2 = slip._l10n_gt_quincena_amount(2)
            slip.l10n_gt_amount_w1 = slip._l10n_gt_semana_amount(1)
            slip.l10n_gt_amount_w2 = slip._l10n_gt_semana_amount(2)
            slip.l10n_gt_amount_w3 = slip._l10n_gt_semana_amount(3)
            slip.l10n_gt_amount_w4 = slip._l10n_gt_semana_amount(4)

    def _l10n_gt_line(self, code):
        """Total de una línea por código (positivo). 0 si no existe."""
        self.ensure_one()
        line = self.line_ids.filtered(lambda l: l.code == code)
        return line.total if line else 0.0

    def _l10n_gt_line_abs(self, code):
        """Total absoluto de una línea por código (para mostrar deducciones sin
        signo en la boleta)."""
        return abs(self._l10n_gt_line(code))

    def _l10n_gt_overtime_hours(self):
        """Horas extra del período (diurnas + nocturnas), según la cantidad de las
        líneas HEXTD/HEXTN."""
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: l.code in ("HEXTD", "HEXTN"))
        return sum(lines.mapped("quantity"))

    def _l10n_gt_amount_words(self, amount):
        """Monto en letras con formato guatemalteco: 'MIL ... CON NN/100'."""
        self.ensure_one()
        amount = abs(amount or 0.0)
        entero = int(amount)
        centavos = int(round((amount - entero) * 100))
        if centavos == 100:  # redondeo hacia arriba
            entero += 1
            centavos = 0
        try:
            from num2words import num2words
            palabras = num2words(entero, lang="es").upper()
        except Exception:
            palabras = (self.company_id.currency_id.amount_to_text(entero)
                        or str(entero)).upper()
        return "%s CON %02d/100" % (palabras, centavos)

    def _l10n_gt_quincena_dates(self, n):
        """Fechas de la 1ª (1-15) o 2ª (16-fin) quincena del período."""
        self.ensure_one()
        df = self.date_from
        if n == 1:
            return df, df.replace(day=15)
        return df.replace(day=16), self.date_to

    def _l10n_gt_quincena_amount(self, n):
        """Monto a pagar en la quincena n, según el método de reparto del recibo.

        - net_half: mitades iguales del líquido (anexo 8.1/8.2). 1ª = 2ª.
        - ordinary_half: 1ª = salario ordinario / 2 (anticipo); 2ª = resto.
        - manual: 1ª = monto fijo del recibo (o del contrato); 2ª = resto.

        En todos los casos la 2ª quincena = líquido del mes − 1ª, para que la boleta
        coincida exactamente con lo pagado (sin discrepancias).
        """
        self.ensure_one()
        net = self._l10n_gt_line("NET")
        method = self.l10n_gt_quincena_method or "net_half"
        if method == "manual":
            fixed = self.l10n_gt_first_quincena_amount
            if not fixed and self.contract_id:
                fixed = self.contract_id.l10n_gt_first_quincena_amount
            first = round(min(fixed, net), 2) if fixed and fixed > 0 else round(net / 2.0, 2)
        elif method == "ordinary_half":
            first = round(self._l10n_gt_line("SALORD") / 2.0, 2)
        else:  # net_half
            first = round(net / 2.0, 2)
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
