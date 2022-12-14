# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


# external reference in product
class ProductTemplate(models.Model):
    _inherit = "product.template"

    inventory_property = fields.Selection([
        ("no_expiry", " No Expiry"),
        ("automated_expiry", "Automated Expiry"),
        ("actual_expiry", "Actual Expiry")], string="Inventory Property")

    @api.constrains('inventory_property', 'use_expiration_date', 'tracking', 'expiration_time')
    def _check_expiration__time(self):
        for rec in self:
            if rec.inventory_property == 'automated_expiry':
                if rec.expiration_time <= 0:
                    raise ValidationError(
                        _('For product with inventory property automated expiry, the expiration time should be grater than zero'))

    @api.onchange('categ_id')
    def onchange_categ_id(self):
        for rec in self:
            if rec.categ_id:
                if rec.categ_id.inventory_property:
                    rec.inventory_property = rec.categ_id.inventory_property

    @api.onchange('inventory_property')
    def onchange_inventory_property(self):
        for rec in self:
            if rec.inventory_property == 'no_expiry':
                rec.write({
                    'tracking': 'none',
                    'use_expiration_date': False,
                })
            elif rec.inventory_property == 'automated_expiry':
                rec.write({
                    'tracking': 'lot',
                    'use_expiration_date': True,
                })
            elif rec.inventory_property == 'actual_expiry':
                rec.write({
                    'tracking': 'lot',
                    'use_expiration_date': True,
                })
