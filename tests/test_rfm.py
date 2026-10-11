from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger
from psycopg2 import IntegrityError


@tagged("post_install", "-at_install")
class TestRfm(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.segment = cls.env["rfm.segment"].create(
            {"name": "Champions", "code": "CHAMP"}
        )

    def test_rfm_score(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Test customer",
                "rfm_recency_score": 5,
                "rfm_frequency_score": 4,
                "rfm_monetary_score": 3,
                "rfm_segment_id": self.segment.id,
            }
        )
        self.assertEqual(partner.rfm_score, "543")
        self.assertIn(partner, self.segment.partner_ids)

    def test_rfm_score_empty(self):
        partner = self.env["res.partner"].create({"name": "No scores"})
        self.assertFalse(partner.rfm_score)

    def test_segment_code_unique(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.env["rfm.segment"].create({"name": "Copy", "code": "CHAMP"})
