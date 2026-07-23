# -*- coding: utf-8 -*-
{
    "name": "Guatemala - Nómina Préstamos y Anticipos",
    "version": "18.0.1.2.0",
    "category": "Human Resources/Payroll",
    "summary": "Anticipos de sueldo flexibles y préstamos con cuotas, con descuento "
               "automático en nómina (§4.11, §4.12).",
    "author": "URBOP / OliveGT",
    "license": "OEEL-1",
    "depends": [
        "l10n_gt_payroll",
        "l10n_gt_payroll_report",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/hr_salary_rule_data.xml",
        "views/l10n_gt_loan_views.xml",
        "views/l10n_gt_advance_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
}
