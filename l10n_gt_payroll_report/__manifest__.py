# -*- coding: utf-8 -*-
{
    "name": "Guatemala - Nómina Reportes",
    "version": "18.0.1.11.0",
    "category": "Human Resources/Payroll",
    "summary": "Boleta de pago, planilla general, reporte de IGSS, costos de "
               "personal, Libro de Salarios e Informe del Empleador (§6).",
    "author": "URBOP / OliveGT",
    "license": "OEEL-1",
    "depends": [
        "l10n_gt_payroll",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_company_views.xml",
        "report/report_actions.xml",
        "report/boleta_pago.xml",
        "report/boleta_quincena.xml",
        "report/boleta_semana.xml",
        "report/comprobante_pago.xml",
        "report/estado_cuenta_contrato.xml",
        "views/hr_payslip_views.xml",
        "views/hr_contract_views.xml",
        "report/planilla_general.xml",
        "report/reporte_igss.xml",
        "report/costos_personal.xml",
        "report/libro_salarios.xml",
        "report/informe_empleador.xml",
    ],
    "installable": True,
    "application": False,
}
