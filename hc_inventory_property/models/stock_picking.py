# -*- coding: utf-8 -*-

from odoo import api, models, fields, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        for picking in self:
            if picking.picking_type_id.code == 'incoming':
                for line in picking.move_line_ids:
                    product = line.product_id
                    if product:
                        if product.inventory_property == 'automated_expiry':
                            if not line.lot_name and not line.lot_id:
                                if line.expiration_date:
                                    line.update({
                                        'lot_name': line.expiration_date.strftime('%d/%m/%Y 00:00:00'),
                                        'expiration_date': line.expiration_date,
                                    })
                        if product.inventory_property == 'actual_expiry':
                            if line.qty_done == 0:
                                line.update({
                                    'expiration_date': False,
                                })
                            if not line.lot_name and not line.lot_id:
                                if line.expiration_date:
                                    line.update({
                                        'lot_name': line.expiration_date.strftime('%d/%m/%Y 00:00:00'),
                                    })

        return super(StockPicking, self).button_validate()
