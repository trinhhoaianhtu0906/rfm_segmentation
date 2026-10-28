{  # noqa: B018
    "name": "RFM Segmentation",
    "version": "19.0.1.1.0",
    "summary": "Score customers by recency, frequency and monetary value",
    "description": "Scores customers every day from their invoices, sales orders "
    "or Point of Sale orders and groups them into RFM segments.",
    "category": "Sales",
    "author": "Tricasia",
    "license": "LGPL-3",
    "depends": ["account"],
    "data": [
        "security/rfm_security.xml",
        "security/ir.model.access.csv",
        "data/rfm_segment_data.xml",
        "data/ir_cron_data.xml",
        "views/rfm_segment_views.xml",
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
        "views/rfm_menus.xml",
    ],
    "application": True,
    "installable": True,
}
