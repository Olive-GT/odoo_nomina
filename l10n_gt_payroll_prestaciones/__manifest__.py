# -*- coding: utf-8 -*-
{
    "name": "Guatemala - Nómina Prestaciones",
    "version": "18.0.1.6.0",
    "category": "Human Resources/Payroll",
    "summary": "Provisiones de prestaciones (aguinaldo, bono 14, indemnización), "
               "pasivo laboral y control de vacaciones (§4.6, §4.7, §4.8).",
    "author": "URBOP / OliveGT",
    "license": "OEEL-1",
    "depends": [
        "l10n_gt_payroll",
        "l10n_gt_payroll_report",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/hr_salary_rule_category_data.xml",
        "data/hr_rule_parameter_data.xml",
        "data/hr_salary_rule_data.xml",
        "views/l10n_gt_benefit_views.xml",
        "views/hr_employee_views.xml",
        "views/hr_payslip_views.xml",
        "report/pasivo_laboral.xml",
        "views/l10n_gt_liability_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
}
