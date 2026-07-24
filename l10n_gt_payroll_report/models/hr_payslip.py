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

    @api.depends("contract_id")
    def _compute_l10n_gt_quincena_method(self):
        for slip in self:
            slip.l10n_gt_quincena_method = (
                slip.contract_id.l10n_gt_quincena_method
                or slip.company_id.l10n_gt_quincena_method or "net_half"
            )

    # ------------------------------------------------------------------
    # Estado de cuenta (pagos del mes)
    # ------------------------------------------------------------------
    l10n_gt_payment_ids = fields.One2many(
        "l10n.gt.payslip.payment", "payslip_id", string="Pagos del mes")
    l10n_gt_net_amount = fields.Monetary(
        "Líquido del mes", compute="_compute_l10n_gt_estado_cuenta", store=True)
    l10n_gt_recover_amount = fields.Monetary(
        "(−) Recuperación de anticipos", compute="_compute_l10n_gt_estado_cuenta",
        store=True)
    l10n_gt_topay_amount = fields.Monetary(
        "Líquido a pagar", compute="_compute_l10n_gt_estado_cuenta", store=True)
    l10n_gt_paid_amount = fields.Monetary(
        "Total pagado", compute="_compute_l10n_gt_estado_cuenta", store=True)
    l10n_gt_pending_amount = fields.Monetary(
        "Saldo pendiente", compute="_compute_l10n_gt_estado_cuenta", store=True)
    l10n_gt_payment_state = fields.Selection(
        selection=[
            ("none", "Sin pagar"),
            ("partial", "Parcial"),
            ("paid", "Pagado"),
        ],
        string="Estado de pago", compute="_compute_l10n_gt_estado_cuenta",
        store=True, default="none",
    )

    @api.depends("line_ids.total", "line_ids.code", "l10n_gt_payment_ids.amount",
                 "l10n_gt_payment_ids.paid", "l10n_gt_payment_ids.benefit_type")
    def _l10n_gt_recover_total(self):
        """Total de recuperación de anticipos capturada en el recibo (líneas de
        tipo 'anticipo_recover'). Reduce el líquido a pagar del mes."""
        self.ensure_one()
        return sum(self.l10n_gt_payment_ids.filtered(
            lambda p: p.benefit_type == "anticipo_recover").mapped("amount"))

    def write(self, vals):
        """Al guardar cambios en las líneas de pago (p. ej. una recuperación de
        anticipo), regenera las quincenas pendientes para que ya reflejen el
        descuento, sin tener que pulsar 'Generar programación'."""
        res = super().write(vals)
        if (not self.env.context.get("l10n_gt_skip_regen")
                and "l10n_gt_payment_ids" in vals):
            for slip in self:
                if (slip.state in ("draft", "verify")
                        and slip._l10n_gt_recover_total() > 0):
                    slip.with_context(
                        l10n_gt_skip_regen=True).action_l10n_gt_generar_pagos()
        return res

    def _compute_l10n_gt_estado_cuenta(self):
        for slip in self:
            net = slip._l10n_gt_line("NET")
            # La recuperación de anticipos reduce el líquido a pagar (se descuenta
            # de las quincenas).
            recover = slip._l10n_gt_recover_total()
            topay = net - recover
            # El saldo del salario solo considera pagos de tipo 'salary'. Las
            # prestaciones (bono 14, aguinaldo…) drenan su propio pasivo, no el
            # líquido del mes.
            paid = sum(slip.l10n_gt_payment_ids.filtered(
                lambda p: p.paid and p.benefit_type == "salary").mapped("amount"))
            slip.l10n_gt_net_amount = net
            slip.l10n_gt_recover_amount = recover
            slip.l10n_gt_topay_amount = topay
            slip.l10n_gt_paid_amount = paid
            slip.l10n_gt_pending_amount = topay - paid
            if paid <= 0.005:
                slip.l10n_gt_payment_state = "none"
            elif paid + 0.005 >= topay:
                slip.l10n_gt_payment_state = "paid"
            else:
                slip.l10n_gt_payment_state = "partial"

    def action_l10n_gt_generar_pagos(self):
        """Genera la programación de pagos según la frecuencia y el método ya
        definidos en el contrato/recibo. No marca los pagos como pagados: es el
        calendario sugerido, que el usuario confirma marcando 'Pagado' conforme
        entrega cada pago. Reemplaza las líneas aún NO pagadas para no alterar el
        historial de lo ya entregado."""
        for slip in self:
            # Solo el salario: conserva lo ya pagado y las prestaciones; regenera
            # únicamente las líneas de salario pendientes.
            slip.l10n_gt_payment_ids.filtered(
                lambda p: not p.paid and p.benefit_type == "salary").unlink()
            paid_total = sum(slip.l10n_gt_payment_ids.filtered(
                lambda p: p.paid and p.benefit_type == "salary").mapped("amount"))
            freq = slip.l10n_gt_payment_frequency or "monthly"
            # Programa completo con los montos plenos (según el método).
            vals = []
            if freq == "biweekly":
                for n in (1, 2):
                    vals.append((
                        "%s quincena" % ("Primera" if n == 1 else "Segunda"),
                        slip._l10n_gt_quincena_dates(n)[1],
                        slip._l10n_gt_quincena_amount(n)))
            elif freq == "weekly":
                for n in (1, 2, 3, 4):
                    vals.append(("Semana %s" % n,
                                 slip._l10n_gt_semana_dates(n)[1],
                                 slip._l10n_gt_semana_amount(n)))
            else:  # monthly
                vals.append(("Pago del mes", slip.date_to, slip._l10n_gt_line("NET")))
            # Descuenta lo ya pagado -> monto PENDIENTE por pagar de cada línea.
            restante_pagado = paid_total
            pendientes = []
            for concepto, fecha, monto in vals:
                aplica = min(restante_pagado, monto)
                restante_pagado -= aplica
                pend = round(monto - aplica, 2)
                if pend > 0:
                    pendientes.append([concepto, fecha, pend])
            # La recuperación de anticipos se reparte SOLO sobre las líneas NO
            # pagadas (lo ya entregado no se toca).
            recover = slip._l10n_gt_recover_total()
            if pendientes and recover > 0:
                k = len(pendientes)
                per = round(recover / k, 2)
                for i, row in enumerate(pendientes):
                    baja = per if i < k - 1 else round(recover - per * (k - 1), 2)
                    row[2] = max(round(row[2] - baja, 2), 0.0)
            for concepto, fecha, pend in pendientes:
                if pend <= 0:
                    continue
                slip.l10n_gt_payment_ids.create({
                    "payslip_id": slip.id,
                    "name": concepto,
                    "date": fecha,
                    "amount": pend,
                    "paid": False,
                    "benefit_type": "salary",
                })
        return True

    def _l10n_gt_money(self, amount):
        """Formatea un monto para las boletas: símbolo de moneda al inicio y
        separador de miles (p. ej. Q10,500.00)."""
        self.ensure_one()
        symbol = (self.company_id.currency_id.symbol or "Q")
        return "%s%s" % (symbol, "{:,.2f}".format(amount or 0.0))

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
