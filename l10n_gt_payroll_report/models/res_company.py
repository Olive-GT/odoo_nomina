# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_gt_payslip_period = fields.Selection(
        selection=[
            ("monthly", "Mensual"),
            ("biweekly", "Quincenal"),
            ("weekly", "Semanal"),
        ],
        string="Frecuencia de pago por defecto",
        default="biweekly",
        help="Frecuencia de pago que tomarán por defecto los contratos NUEVOS de "
             "esta empresa. La frecuencia real se define en cada contrato (puede "
             "variar por empleado). El cálculo de la nómina siempre es mensual; "
             "esto solo define en cuántos comprobantes se reparte el pago.",
    )
    l10n_gt_quincena_method = fields.Selection(
        selection=[
            ("net_half", "Mitades iguales (líquido ÷ 2)"),
            ("ordinary_half", "Anticipo del ordinario (1ª = ordinario ÷ 2; 2ª el resto)"),
        ],
        string="Método de reparto de quincenas",
        default="net_half",
        help="Cómo se reparte el pago mensual en dos quincenas cuando NO se captura "
             "un monto manual:\n"
             "- Mitades iguales: cada quincena paga la mitad del líquido del mes "
             "(1ª = 2ª). Es el método del documento (anexo 8.1/8.2).\n"
             "- Anticipo del ordinario: la 1ª quincena paga la mitad del salario "
             "ordinario (sin bonificación ni deducciones) y la 2ª liquida el resto "
             "(otra mitad + bonificación − IGSS/ISR/descuentos). La 2ª suele ser mayor.\n\n"
             "En ambos casos puede sobrescribirse con un monto manual en el contrato "
             "(fijo por empleado) o en el recibo (solo ese mes).",
    )
