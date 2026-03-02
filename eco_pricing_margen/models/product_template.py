# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools.float_utils import float_round


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # ================================
    # ULTIMO COSTO DE FACTURA
    # ================================
    x_cost_base = fields.Float(
        string="Costo Base Comercial",
        company_dependent=True,
    )

    # ================================
    # UTILIDADES POR CANAL
    # ================================
    x_utility_pct_tat = fields.Float(string="Utility % TAT", company_dependent=True)
    x_utility_pct_pos = fields.Float(string="Utility % POS", company_dependent=True)
    x_utility_pct_mayorista = fields.Float(string="Utility % Mayorista", company_dependent=True)
    x_utility_pct_oferta = fields.Float(string="Utility % Oferta", company_dependent=True)

    # ================================
    # PRECIOS DISPLAY (CON IVA)
    # ================================
    x_final_price_tat = fields.Float(compute="_compute_prices", store=True)
    x_final_price_pos = fields.Float(compute="_compute_prices", store=True)
    x_final_price_mayorista = fields.Float(compute="_compute_prices", store=True)
    x_final_price_oferta = fields.Float(compute="_compute_prices", store=True)

    @api.depends(
        "x_cost_base",
        "x_utility_pct_tat",
        "x_utility_pct_pos",
        "x_utility_pct_mayorista",
        "x_utility_pct_oferta",
        "taxes_id",
        "taxes_id.amount",
        "company_id",
    )
    def _compute_prices(self):
        for product in self:
            tax_rate = 0.0
            sale_taxes = product.taxes_id.filtered(
                lambda t: t.type_tax_use == "sale" and t.amount_type == "percent"
            )
            if sale_taxes:
                tax_rate = sum(sale_taxes.mapped("amount")) / 100.0

            def compute_price_incl(cost, utility):
                if not cost:
                    return 0.0
                price_excl = cost * (1 + (utility or 0.0) / 100.0)
                price_incl = price_excl * (1 + tax_rate)
                return float_round(price_incl, precision_rounding=product.currency_id.rounding)

            product.x_final_price_tat = compute_price_incl(product.x_cost_base, product.x_utility_pct_tat)
            product.x_final_price_pos = compute_price_incl(product.x_cost_base, product.x_utility_pct_pos)
            product.x_final_price_mayorista = compute_price_incl(product.x_cost_base, product.x_utility_pct_mayorista)
            product.x_final_price_oferta = compute_price_incl(product.x_cost_base, product.x_utility_pct_oferta)

    # ================================
    # PRECIOS SIN IVA (PARA LISTAS)
    # ================================
    def _channel_prices_excl(self):
        self.ensure_one()
        cost = self.x_cost_base or 0.0
        if not cost:
            return {
                "T.A.T": 0.0,
                "P.O.S": 0.0,
                "MAYORISTA": 0.0,
                "OFERTAS": 0.0,
            }

        def p(utility):
            price_excl = cost * (1 + (utility or 0.0) / 100.0)
            return float_round(price_excl, precision_rounding=self.currency_id.rounding)

        return {
            "T.A.T": p(self.x_utility_pct_tat),
            "P.O.S": p(self.x_utility_pct_pos),
            "MAYORISTA": p(self.x_utility_pct_mayorista),
            "OFERTAS": p(self.x_utility_pct_oferta),
        }

    # ================================
    # SINCRONIZAR LISTAS
    # ================================
    def _sync_pricelist_items(self):
        Pricelist = self.env["product.pricelist"].sudo()
        Item = self.env["product.pricelist.item"].sudo()

        for product in self:
            prices = product._channel_prices_excl()

            for pl_name, fixed_price in prices.items():
                if fixed_price <= 0:
                    continue

                pricelist = Pricelist.search([("name", "=", pl_name)], limit=1)
                if not pricelist:
                    continue

                item = Item.search([
                    ("pricelist_id", "=", pricelist.id),
                    ("applied_on", "=", "1_product"),
                    ("product_tmpl_id", "=", product.id),
                ], limit=1)

                vals = {
                    "pricelist_id": pricelist.id,
                    "applied_on": "1_product",
                    "product_tmpl_id": product.id,
                    "compute_price": "fixed",
                    "fixed_price": fixed_price,
                }

                if item:
                    item.write(vals)
                else:
                    Item.create(vals)

    def write(self, vals):
        res = super().write(vals)

        watched = {
            "x_cost_base",
            "x_utility_pct_tat",
            "x_utility_pct_pos",
            "x_utility_pct_mayorista",
            "x_utility_pct_oferta",
        }

        if watched.intersection(vals.keys()):
            self._sync_pricelist_items()

        return res
