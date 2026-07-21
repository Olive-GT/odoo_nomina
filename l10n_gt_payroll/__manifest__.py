# -*- coding: utf-8 -*-
{
    "name": "Guatemala - Nómina",
    "version": "18.0.1.0.0",
    "category": "Human Resources/Payroll",
    "summary": "Reglas, estructuras y parámetros legales de la nómina ordinaria "
               "guatemalteca (IGSS laboral/patronal, Bonificación Incentivo, "
               "horas extra).",
    "author": "URBOP / OliveGT",
    "license": "OEEL-1",  # depende de hr_payroll (Enterprise)
    "depends": [
        "l10n_gt_hr",
        "hr_payroll",
        "hr_work_entry_contract",
    ],
    "data": [
        "security/l10n_gt_payroll_security.xml",
        "data/hr_salary_rule_category_data.xml",
        "data/hr_rule_parameter_data.xml",
        "data/hr_payslip_input_type_data.xml",
        "data/hr_payroll_structure_type_data.xml",
        "data/hr_payroll_structure_data.xml",
        "data/hr_salary_rule_data.xml",
        "views/hr_payslip_run_views.xml",
    ],
    "installable": True,
    "application": False,
}
