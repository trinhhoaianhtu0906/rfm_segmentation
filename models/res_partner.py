from odoo import api, fields, models

RFM_GROUP = "rfm_segmentation.group_rfm_user"


class ResPartner(models.Model):
    _inherit = "res.partner"

    rfm_recency_score = fields.Integer(string="Recency score", groups=RFM_GROUP)
    rfm_frequency_score = fields.Integer(string="Frequency score", groups=RFM_GROUP)
    rfm_monetary_score = fields.Integer(string="Monetary score", groups=RFM_GROUP)
    rfm_score = fields.Char(
        string="RFM score",
        compute="_compute_rfm_score",
        store=True,
        groups=RFM_GROUP,
    )
    rfm_segment_id = fields.Many2one(
        "rfm.segment",
        string="RFM segment",
        index=True,
        groups=RFM_GROUP,
    )

    @api.depends("rfm_recency_score", "rfm_frequency_score", "rfm_monetary_score")
    def _compute_rfm_score(self):
        for partner in self:
            scores = (
                partner.rfm_recency_score,
                partner.rfm_frequency_score,
                partner.rfm_monetary_score,
            )
            partner.rfm_score = "".join(map(str, scores)) if all(scores) else False
