# -*- coding: utf-8 -*-
{
    "name": "Guatemala - Nómina Reportes Excel",
    "version": "18.0.1.0.0",
    "category": "Human Resources/Payroll",
    "summary": "Nómina de sueldos y salarios en Excel (.xlsx) desde el lote, con el "
               "formato del cliente (§6.2). Requiere report_xlsx (OCA).",
    "author": "URBOP / OliveGT",
    "license": "OEEL-1",
    "depends": [
        "l10n_gt_payroll_report",
        "report_xlsx",
    ],
    "data": [
        "report/report_actions.xml",
    ],
    "installable": True,
    "application": False,
}
