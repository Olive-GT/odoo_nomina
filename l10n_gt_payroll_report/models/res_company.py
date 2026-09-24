# -*- coding: utf-8 -*-
# Los defaults de frecuencia y método de reparto se retiraron de la empresa: se
# definen en el contrato (por empleado) y se ajustan por recibo.
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Firmas al pie de la Nómina de sueldos y salarios.
    l10n_gt_payroll_prepared_by = fields.Char(
        "Nómina: elaborado por",
        help="Nombre que firma 'Elaborado por' al pie de la nómina de sueldos.")
    l10n_gt_payroll_approved_by = fields.Char(
        "Nómina: aprobado por",
        help="Nombre que firma 'Aprobado por' al pie de la nómina de sueldos.")
