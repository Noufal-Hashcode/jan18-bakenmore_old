# -*- coding: utf-8 -*-

from odoo import models, fields, api


# item Group in product category

class ProductCategory(models.Model):
    _inherit = "product.category"

    inventory_property = fields.Selection([
        ("no_expiry", " No Expiry"),
        ("automated_expiry", "Automated Expiry"),
        ("actual_expiry", "Actual Expiry")], string="Inventory Property")
