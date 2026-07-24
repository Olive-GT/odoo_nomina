# -*- coding: utf-8 -*-
{
    "name": "Guatemala - Nómina Liquidaciones",
    "version": "18.0.1.2.0",
    "category": "Human Resources/Payroll",
    "summary": "Finiquito como recibo de liquidación: indemnización y prestaciones "
               "proporcionales dentro del recibo/estado de cuenta (§4.16, §5).",
    "author": "URBOP / OliveGT",
    "license": "OEEL-1",
    "depends": [
        "l10n_gt_payroll_prestaciones",
        "l10n_gt_payroll_report",
    ],
    "data": [
        "report/l10n_gt_settlement_report.xml",
        "views/l10n_gt_settlement_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
}
