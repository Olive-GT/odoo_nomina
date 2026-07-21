# -*- coding: utf-8 -*-
{
    "name": "Guatemala - Nómina Contabilidad",
    "version": "18.0.1.0.0",
    "category": "Human Resources/Payroll",
    "summary": "Cuentas contables por concepto y póliza de nómina, con generación "
               "de la póliza independiente del módulo de Contabilidad (§6.9, §2.9).",
    "author": "URBOP / OliveGT",
    "license": "OEEL-1",
    "depends": [
        "l10n_gt_payroll",
        "account",
    ],
    "data": [
        "views/hr_salary_rule_views.xml",
        "report/l10n_gt_poliza_report.xml",
        "views/hr_payslip_run_views.xml",
    ],
    "installable": True,
    "application": False,
}
