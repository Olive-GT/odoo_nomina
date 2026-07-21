# -*- coding: utf-8 -*-
{
    "name": "Guatemala - Nómina Liquidaciones",
    "version": "18.0.1.0.0",
    "category": "Human Resources/Payroll",
    "summary": "Liquidaciones laborales, indemnización y finiquito (§4.16, §5).",
    "author": "URBOP / OliveGT",
    "license": "OEEL-1",
    "depends": [
        "l10n_gt_payroll_prestaciones",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "report/l10n_gt_settlement_report.xml",
        "views/l10n_gt_settlement_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
}
