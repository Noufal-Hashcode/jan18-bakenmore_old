# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    hc_picking_id = fields.Many2one('stock.picking', 'Picking', copy=False)
    mo_picking_count = fields.Integer(string='Delivery Orders', compute='_compute_mo_picking_count', copy=False)

    @api.depends('hc_picking_id')
    def _compute_mo_picking_count(self):
        for order in self:
            if order.hc_picking_id:
                picking_ids = self.env['stock.picking'].search([
                    ('id', '=', order.hc_picking_id.id)
                ])
                order.mo_picking_count = len(picking_ids)
            else:
                order.mo_picking_count = 0

    def action_view_hc_mo_delivery(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
        pickings = self.env['stock.picking'].search([
            ('id', '=', self.hc_picking_id.id)
        ])
        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings.ids)]
        elif pickings:
            form_view = [(self.env.ref('stock.view_picking_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = pickings.id
        action['context'] = dict(self._context, default_origin=self.name, create=False)
        return action

    def action_confirm(self):
        self._check_company()
        for production in self:
            if production.bom_id:
                production.consumption = production.bom_id.consumption
            # In case of Serial number tracking, force the UoM to the UoM of product
            if production.product_tracking == 'serial' and production.product_uom_id != production.product_id.uom_id:
                production.write({
                    'product_qty': production.product_uom_id._compute_quantity(production.product_qty,
                                                                               production.product_id.uom_id),
                    'product_uom_id': production.product_id.uom_id
                })
                for move_finish in production.move_finished_ids.filtered(
                        lambda m: m.product_id == production.product_id):
                    move_finish.write({
                        'product_uom_qty': move_finish.product_uom._compute_quantity(move_finish.product_uom_qty,
                                                                                     move_finish.product_id.uom_id),
                        'product_uom': move_finish.product_id.uom_id
                    })
            production.move_raw_ids._adjust_procure_method()
            if production.move_raw_ids:
                picking_type = self.env['stock.picking.type'].search([('sequence_code', '=', 'PC'),
                                                                      ('warehouse_id', '=', production.picking_type_id.warehouse_id.id)])
                print("picking_type", picking_type)
                if picking_type:
                    picking = self.env['stock.picking'].search(
                        [('state', 'not in', ['done', 'cancel']),
                         ('picking_type_id', '=', picking_type.id)], limit=1)
                    print("kkkkklskdlskdmsdksddfsdf")
                    if picking:
                        print("kkkkklskdlskdmsdksderwer")
                        picking_products_list = []
                        for move_hc in picking.move_ids_without_package:
                            picking_products_list.append(move_hc.product_id.id)
                        move_data_list = []
                        for hc_move in production.move_raw_ids:
                            if hc_move.product_uom_qty > 0:
                                if hc_move.product_id.id not in picking_products_list:
                                    move_data_dict = {
                                        'name': 'Mo Picking Move',
                                        'location_id': picking_type.default_location_src_id.id,
                                        'location_dest_id': picking_type.default_location_dest_id.id,
                                        'product_id': hc_move.product_id.id,
                                        'product_uom': hc_move.product_uom.id,
                                        'product_uom_qty': hc_move.product_uom_qty,
                                    }
                                    move_data_list.append((0, 0, move_data_dict))
                        for hc_move_2 in production.move_raw_ids:
                            for move_hc_2 in picking.move_ids_without_package:
                                if move_hc_2.product_id.id == hc_move_2.product_id.id:
                                    move_hc_2.product_uom_qty = move_hc_2.product_uom_qty + hc_move_2.product_uom_qty
                        if move_data_list:
                            picking.update({
                                'move_ids_without_package': move_data_list
                            })
                        hc_picking = picking
                    else:
                        print("kkkkklskdlskdmsdksd")
                        move_data_list = []
                        for hc_move in production.move_raw_ids:
                            if hc_move.product_uom_qty > 0:
                                move_data_dict = {
                                    'name': 'Mo Picking Move',
                                    'location_id': picking_type.default_location_src_id.id,
                                    'location_dest_id': picking_type.default_location_dest_id.id,
                                    'product_id': hc_move.product_id.id,
                                    'product_uom': hc_move.product_uom.id,
                                    'product_uom_qty': hc_move.product_uom_qty,
                                }
                                move_data_list.append((0, 0, move_data_dict))
                        hc_picking = self.env['stock.picking'].create({
                            'picking_type_id': picking_type.id,
                            'location_id': picking_type.default_location_src_id.id,
                            'location_dest_id': picking_type.default_location_dest_id.id,
                            'move_ids_without_package': move_data_list
                        })
                    if hc_picking:
                        production.hc_picking_id = hc_picking
            (production.move_finished_ids)._action_confirm(merge=False)
            production.workorder_ids._action_confirm()
        # run scheduler for moves forecasted to not have enough in stock
        self.move_raw_ids._trigger_scheduler()
        self.picking_ids.filtered(
            lambda p: p.state not in ['cancel', 'done']).action_confirm()
        # Force confirm state only for draft production not for more advanced state like
        # 'progress' (in case of backorders with some qty_producing)
        self.filtered(lambda mo: mo.state == 'draft').state = 'confirmed'
        return True