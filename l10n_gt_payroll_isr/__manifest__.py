# -*- coding: utf-8 -*-
{
    "name": "Guatemala - Nómina ISR Asalariados",
    "version": "18.0.1.1.0",
    "category": "Human Resources/Payroll",
    "summary": "Proyección anual del ISR asalariados y su retención mensual (§4.10).",
    "author": "URBOP / OliveGT",
    "license": "OEEL-1",
    "depends": [
        "l10n_gt_payroll",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/hr_salary_rule_data.xml",
        "views/l10n_gt_isr_projection_views.xml",
        "views/l10n_gt_isr_deduction_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
}
