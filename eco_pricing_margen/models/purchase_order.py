# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _update_product_cost(self):
        """Actualiza el costo del producto con el precio unitario de la compra."""
        for line in self:
            if line.product_id and line.state in ['purchase', 'done']:
                # Actualiza el standard_price con el valor neto de la compra
                # Esto se ejecuta automáticamente cuando se valida la compra
                line.product_id.product_tmpl_id.standard_price = line.price_unit

    def write(self, vals):
        res = super(PurchaseOrderLine, self).write(vals)
        # Al confirmar o actualizar la línea de compra, enviamos el costo al producto
        self._update_product_cost()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        lines = super(PurchaseOrderLine, self).create(vals_list)
        # Si la línea se crea en un pedido ya confirmado, actualizar costo
        lines._update_product_cost()
        return lines


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def button_confirm(self):
        """Sobrescribir confirmación para actualizar costos de productos."""
        res = super(PurchaseOrder, self).button_confirm()
        # Al confirmar el pedido, actualizar costos de todos los productos
        for line in self.order_line:
            if line.product_id:
                line.product_id.product_tmpl_id.standard_price = line.price_unit
        return res

