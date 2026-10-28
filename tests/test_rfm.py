from datetime import timedelta

from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger
from psycopg2 import IntegrityError

from ..models.rfm_calculator import quintile_scores


@tagged("post_install", "-at_install")
class TestRfm(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.segment = cls.env["rfm.segment"].create(
            {"name": "Test segment", "code": "TEST"}
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
        self.assertEqual(self.segment.partner_count, 1)

    def test_rfm_score_empty(self):
        partner = self.env["res.partner"].create({"name": "No scores"})
        self.assertFalse(partner.rfm_score)

    def test_segment_code_unique(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.env["rfm.segment"].create({"name": "Copy", "code": "TEST"})

    def test_segment_range_check(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.env["rfm.segment"].create(
                {"name": "Bad", "code": "BAD", "r_min": 4, "r_max": 2}
            )

    def test_quintile_scores(self):
        self.assertEqual(quintile_scores([]), [])
        self.assertEqual(quintile_scores([7]), [1])
        self.assertEqual(quintile_scores([10, 20, 30, 40, 50]), [1, 2, 3, 4, 5])
        # Ties share the score of the lowest rank among them.
        self.assertEqual(quintile_scores([1, 1, 1, 1, 2]), [1, 1, 1, 1, 5])
        self.assertEqual(
            quintile_scores(list(range(10))), [1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
        )

    def test_default_segments_cover_every_score(self):
        segments = self.env["rfm.segment"].search([("code", "!=", "TEST")])
        for r in range(1, 6):
            for f in range(1, 6):
                self.assertTrue(segments._match(r, f), f"No segment for R={r} F={f}")


class RfmSourceCommon(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for xmlid in (
            "rfm_segmentation.group_rfm_manager",
            "sales_team.group_sale_manager",
            "point_of_sale.group_pos_manager",
        ):
            group = cls.env.ref(xmlid, raise_if_not_found=False)
            if group:
                cls.env.user.group_ids |= group
        cls.today = fields.Date.today()
        cls.calculator = cls.env["rfm.calculator"]
        cls.company = cls.env.company
        cls.company.rfm_period_months = 12
        cls.customers = cls.env["res.partner"].create(
            [{"name": f"RFM customer {i}"} for i in range(5)]
        )

    def _days_ago(self, days):
        return self.today - timedelta(days=days)

    def _scores(self, partner):
        return (
            partner.rfm_recency_score,
            partner.rfm_frequency_score,
            partner.rfm_monetary_score,
        )


@tagged("post_install", "-at_install")
class TestRfmInvoices(RfmSourceCommon):
    def _invoice(self, partner, days, amount, move_type="out_invoice"):
        return self._create_invoice_one_line(
            move_type=move_type,
            partner_id=partner,
            price_unit=amount,
            invoice_date=self._days_ago(days),
            post=True,
        )

    def test_fetch_invoices(self):
        customer = self.customers[0]
        contact = self.env["res.partner"].create(
            {"name": "Contact", "parent_id": customer.id}
        )
        self._invoice(customer, 10, 1000)
        self._invoice(contact, 3, 500)
        self._invoice(customer, 2, 200, move_type="out_refund")
        self._invoice(customer, 400, 9999)  # outside the 12 month period
        self._create_invoice_one_line(
            partner_id=customer, price_unit=777, invoice_date=self.today
        )  # draft

        data = self.calculator._fetch_account_move(self.company)

        self.assertEqual(list(data), [customer.id])
        last_date, count, amount = data[customer.id]
        self.assertEqual(last_date, self._days_ago(3))
        self.assertEqual(count, 2)
        self.assertAlmostEqual(amount, 1300)

    def test_compute_scores_and_segments(self):
        # Customer i bought i+1 times, the last time 10*(5-i) days ago.
        for i, customer in enumerate(self.customers):
            for n in range(i + 1):
                self._invoice(customer, 10 * (5 - i) + n, 100)
        champions = self.env.ref("rfm_segmentation.segment_champions")
        stale = self.env["res.partner"].create(
            {
                "name": "Stale",
                "rfm_recency_score": 5,
                "rfm_frequency_score": 5,
                "rfm_monetary_score": 5,
                "rfm_segment_id": champions.id,
            }
        )

        self.calculator._compute_rfm(self.company)

        best, worst = self.customers[4], self.customers[0]
        self.assertEqual(self._scores(worst), (1, 1, 1))
        self.assertEqual(self._scores(best), (5, 5, 5))
        self.assertEqual(best.rfm_score, "555")
        self.assertEqual(best.rfm_frequency, 5)
        self.assertEqual(best.rfm_recency_days, 10)
        self.assertAlmostEqual(best.rfm_monetary, 500)
        self.assertEqual(best.rfm_segment_id, champions)
        self.assertEqual(
            worst.rfm_segment_id, self.env.ref("rfm_segmentation.segment_lost")
        )
        self.assertFalse(stale.rfm_score)
        self.assertFalse(stale.rfm_segment_id)
        self.assertTrue(self.company.rfm_last_compute)


@tagged("post_install", "-at_install")
class TestRfmSaleOrders(RfmSourceCommon):
    def test_fetch_sale_orders(self):
        if "sale.order" not in self.env:
            self.skipTest("sale is not installed")
        customer = self.customers[0]
        orders = self.env["sale.order"].create(
            [
                {
                    "partner_id": customer.id,
                    "order_line": [
                        Command.create(
                            {"product_id": self.product_a.id, "price_unit": price}
                        )
                    ],
                }
                for price in (300, 700, 50)
            ]
        )
        orders[:2].action_confirm()
        orders[0].date_order = fields.Datetime.now() - timedelta(days=20)
        orders[1].date_order = fields.Datetime.now() - timedelta(days=5)

        data = self.calculator._fetch_sale_order(self.company)

        last_date, count, amount = data[customer.id]
        self.assertEqual(last_date, self._days_ago(5))
        self.assertEqual(count, 2)
        self.assertAlmostEqual(amount, 1000)


@tagged("post_install", "-at_install")
class TestRfmPosOrders(RfmSourceCommon):
    def test_fetch_pos_orders(self):
        if "pos.order" not in self.env:
            self.skipTest("point_of_sale is not installed")
        customer = self.customers[0]
        config = self.env["pos.config"].create({"name": "RFM shop"})
        session = self.env["pos.session"].create(
            {"config_id": config.id, "user_id": self.env.uid}
        )

        def order(partner, days, total, tax, state="paid"):
            return {
                "session_id": session.id,
                "partner_id": partner.id,
                "date_order": fields.Datetime.now() - timedelta(days=days),
                "amount_total": total,
                "amount_tax": tax,
                "amount_paid": total,
                "amount_return": 0,
                "state": state,
            }

        self.env["pos.order"].create(
            [
                order(customer, 8, 110, 10),
                order(customer, 1, 55, 5),
                order(customer, 1, 999, 0, state="cancel"),
                order(self.env["res.partner"], 1, 999, 0),  # anonymous
            ]
        )

        data = self.calculator._fetch_pos_order(self.company)

        self.assertEqual(list(data), [customer.id])
        last_date, count, amount = data[customer.id]
        self.assertEqual(last_date, self._days_ago(1))
        self.assertEqual(count, 2)
        self.assertAlmostEqual(amount, 150)
