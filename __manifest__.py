{  # noqa: B018
    "name": "RFM Segmentation",
    "version": "19.0.1.0.0",
    "summary": "Score customers by recency, frequency and monetary value",
    "category": "Sales",
    "author": "Tricasia",
    "license": "LGPL-3",
    "depends": ["contacts"],
    "data": [
        "security/rfm_security.xml",
        "security/ir.model.access.csv",
        "views/rfm_segment_views.xml",
        "views/res_partner_views.xml",
        "views/rfm_menus.xml",
    ],
    "application": True,
    "installable": True,
}
