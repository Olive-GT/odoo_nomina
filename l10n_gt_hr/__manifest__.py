# -*- coding: utf-8 -*-
{
    "name": "Guatemala - Datos de RRHH / Nómina",
    "version": "18.0.1.1.0",
    "category": "Human Resources/Payroll",
    "summary": "Datos maestros guatemaltecos para empleados y contratos "
               "(DPI, NIT, IGSS, circunscripción económica, salario mínimo).",
    "author": "URBOP / OliveGT",
    "license": "LGPL-3",
    "depends": [
        "hr",
        "hr_contract",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/l10n_gt_economic_zone_data.xml",
        "views/l10n_gt_economic_zone_views.xml",
        "views/hr_employee_views.xml",
        "views/hr_contract_views.xml",
    ],
    "installable": True,
    "application": False,
}
