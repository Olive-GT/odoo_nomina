# -*- coding: utf-8 -*-
{
    "name": "Guatemala - Nómina: horas extra detectadas por asistencia",
    "version": "18.0.1.0.0",
    "category": "Human Resources/Payroll",
    "summary": "Muestra en cada recibo (y en la lista del lote) las horas extra que "
               "registra la asistencia contra el horario del contrato, como "
               "RECOMENDACIÓN: nunca se suman solas al recibo.",
    "author": "URBOP / OliveGT",
    "license": "OEEL-1",
    "depends": [
        "l10n_gt_payroll",
        "hr_attendance",
    ],
    "data": [
        "views/hr_payslip_views.xml",
    ],
    "installable": True,
    "application": False,
}
