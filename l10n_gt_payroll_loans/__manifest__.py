# -*- coding: utf-8 -*-
{
    "name": "Guatemala - Nómina Anticipos",
    "version": "18.0.1.8.0",
    "category": "Human Resources/Payroll",
    "summary": "Anticipos de sueldo como líneas del Estado de Cuenta del recibo "
               "(entrega y recuperación flexible) (§4.11).",
    "author": "URBOP / OliveGT",
    "license": "OEEL-1",
    "depends": [
        "l10n_gt_payroll",
        "l10n_gt_payroll_report",
    ],
    "data": [
        "report/anticipos.xml",
        "views/l10n_gt_advance_views.xml",
    ],
    "installable": True,
    "application": False,
}
