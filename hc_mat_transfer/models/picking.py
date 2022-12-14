# -*- coding: utf-8 -*-

import tempfile
import binascii
from datetime import datetime
from odoo.exceptions import Warning, UserError, ValidationError
from odoo import models, fields, exceptions, api, _
from odoo.modules.module import get_module_resource

import logging

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)

try:
    import xlrd
except ImportError:
    _logger.debug('Cannot `import xlrd`.')
try:
    import base64
except ImportError:
    _logger.debug('Cannot `import base64`.')


class Inherit_Stock_Picking(models.Model):
    _inherit = 'stock.picking'

    is_import = fields.Boolean("import records", default=False)


class ImportPicking(models.TransientModel):
    _name = "import.picking1"
    _description = "Import Picking"

    def _get_transfer_template(self):
        file = get_module_resource('hc_mat_transfer','sample_file','import_picking.xlsx')
        self.transfer_template = base64.b64encode(open(file, "rb").read())

    seq = fields.Char(string="Name")
    file = fields.Binary('File')
    # import_option = fields.Selection([('csv', 'CSV File'),('xls', 'XLS File')],string='Select',default='xls')
    picking_type_id = fields.Many2one('stock.picking.type', 'Picking Type')
    location_id = fields.Many2one(
        'stock.location', "Source Location Zone",
        default=lambda self: self.env['stock.picking.type'].browse(
            self._context.get('default_picking_type_id')).default_location_src_id,
        required=True,
    )
    location_dest_id = fields.Many2one(
        'stock.location', "Destination Location Zone",
        default=lambda self: self.env['stock.picking.type'].browse(
            self._context.get('default_picking_type_id')).default_location_dest_id,
        required=True,
    )
    transfer_template = fields.Binary('Template', compute="_get_transfer_template")


    def download_sample_file(self):
        return {
            'type': 'ir.actions.act_url',
            'name': 'Transfer',
            'url': '/web/content/import.picking1/%s/transfer_template/import_picking.xlsx?download=true' % (self.id),
        }

    @api.onchange('picking_type_id')
    def onchange_picking_type_id(self):
        """
        it is used to set the location and destination location from picking type.
        """
        if self.picking_type_id:
            self.location_id = self.picking_type_id.default_location_src_id.id
            self.location_dest_id = self.picking_type_id.default_location_dest_id.id
            rcode = _('%s') % self.picking_type_id.sequence_id.name
            print("rcode", rcode)
            self.seq = self.env['ir.sequence'].next_by_code(rcode)
            print(self.seq)

    def create_picking(self, values):
        """
        create a picking from data.
        """
        picking_obj = self.env['stock.picking']
        print("in", values.get('seq'))
        picking = picking_obj.search([('name', '=', values.get('seq'))])
        if picking:
            lines = self.make_picking_line(values, picking)
            return lines
        else:
            # pick_date = self._get_date(values.get('date'))
            vals = {
                'name' : values.get('seq'),
                'partner_id': False,
                'picking_type_id': values.get('picking_type_id'),
                'location_id': values.get('location_id'),
                'location_dest_id': values.get('location_dest_id'),
                'origin': values.get('origin'),
                'is_import': True
            }
            print (values.get('seq'))
            pick_id = picking_obj.create(vals)
            lines = self.make_picking_line(values, pick_id)
            # return pick_id

    def make_picking_line(self, values, pick_id):
        """
        it is used to create stock move and stock move line from data.
        """
        product_obj = self.env['product.product'].sudo()
        tmpl_obj= self.env['product.template'].sudo()
        stock_lot_obj = self.env['stock.production.lot'].sudo()
        stock_move_obj = self.env['stock.move'].sudo()
        stock_move_line_obj = self.env['stock.move.line'].sudo()
        expiry_date = False
        lot_id = False

        product_id = product_obj.search(
            [('default_code', '=', values.get('default_code'))])

        if not product_id:
            tmpl_id = tmpl_obj.search(
                [('mgo_code', '=', values.get('mgo_code'))])
            print(values.get('mgo_code'),tmpl_id)

            product_id = product_obj.search([('product_tmpl_id', '=', tmpl_id.id)])
            print(product_id)
        if not product_id:
            raise ValidationError(
                _('Product is not available "%s" .') % values.get('default_code'))

        if product_id.use_expiration_date and not values.get('expiry_date') == '':
            expiry_date = self._get_date(values.get('expiry_date'))
        if values.get('lot') != '':
            if values.get('lot'):
                # prdtmpl_obj = self.env['']
                lot_id = stock_lot_obj.search([('company_id', '=', pick_id.company_id.id), ('name','=',values.get('lot')),('product_id','=',product_id.id)])
                if not lot_id:
                    lot_vals={
                        'name': values.get('lot'),
                        'product_id': product_id.id,
                        'company_id': pick_id.company_id.id,
                        'expiration_date': expiry_date,
                        'use_date' : expiry_date,
                        'removal_date' : expiry_date,
                        'alert_date' : expiry_date
                    }
                    lot_id = stock_lot_obj.create(lot_vals)

        move = stock_move_obj.create({
            'product_id': product_id.id,
            'name': product_id.name,
            'product_uom_qty': values.get('quantity'),
            'picking_id': pick_id.id,
            'location_id': pick_id.location_id.id,
            'date': pick_id.scheduled_date,
            'location_dest_id': pick_id.location_dest_id.id,
            'product_uom': product_id.uom_id.id,
            'picking_type_id': self.picking_type_id.id,
            'state': 'confirmed',

        })

        move_line = stock_move_line_obj.create({
            'picking_id': pick_id.id,
            'location_id': pick_id.location_id.id,
            'location_dest_id': pick_id.location_dest_id.id,
            'qty_done': values.get('quantity'),
            'product_uom_qty':values.get('quantity'),
            'product_id': product_id.id,
            'move_id': move.id,
            'lot_id': lot_id.id if lot_id else False,
            'lot_name':lot_id.name if lot_id else False,
            'expiration_date':lot_id.expiration_date if lot_id else False,
            'product_uom_id': product_id.uom_id.id,
        })
        move_line._onchange_lot_id()
        # return True

    def _get_date(self, date):
        """
        it is used to check the dateformat
        """
        DATETIME_FORMAT = "%Y-%m-%d"
        if date:
            try:
                i_date = datetime.strptime(date, DATETIME_FORMAT).date()
            except Exception:
                raise ValidationError(
                    _('Wrong Date Format. Date Should be in format YYYY-MM-DD.'))
            return i_date
        else:
            raise ValidationError(
                _('Date field is blank in sheet Please add the date.'))

    def import_picking(self):
        """
        it is used to check the file format and preapre values for create picking.
        """
        if not self.file:
            raise ValidationError(_("Please select a file first then proceed"))
        else:
            try:
                fp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
                fp.write(binascii.a2b_base64(self.file))
                fp.seek(0)
                values = {}
                workbook = xlrd.open_workbook(fp.name)
                sheet = workbook.sheet_by_index(0)
            except Exception:
                raise ValidationError(_("Not a valid file!"))
            list_col = ['INTERNAL REFERENCE','MAGENTO REFERENCE','LOT NUMBER','EXPIRY DATE','QUANTITY']
            for row_no in range(sheet.nrows):

                if row_no <= 0:
                    line_fields = list(map(lambda row: isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value),
                                           sheet.row(row_no)))

                    for col in line_fields:
                        if not col in list_col:
                            raise ValidationError(
                                _('Wrong Column name %s.', col))
                else:
                    line = list(map(lambda row: isinstance(row.value, bytes) and row.value.encode(
                        'utf-8') or str(row.value), sheet.row(row_no)))
                    # if line[1] != '':
                    #     if line[1].split('/'):
                    #         if len(line[1].split('/')) > 1:
                    #             raise ValidationError(
                    #                 _('Wrong Date Format. Date Should be in format YYYY-MM-DD.'))
                    #         if len(line[1]) > 8 or len(line[1]) < 5:
                    #             raise ValidationError(
                    #                 _('Wrong Date Format. Date Should be in format YYYY-MM-DD.'))

                    if line[0] == '' and line[1] == '':
                        raise ValidationError(
                            _('INTERNAL REFERENCE or MAGENTO REFERENCE  to be present'))

                    if line[4] == '':
                        raise ValidationError(_('QUANTITY Not Available'))

                    if line[3] != '':
                        expiry_date_float = int(float(line[3]))
                        expiry_date = datetime(
                        *xlrd.xldate_as_tuple(expiry_date_float, workbook.datemode))
                        expiry_date_string = expiry_date.date().strftime('%Y-%m-%d')
                    else:
                        expiry_date_string = False
                    print(line[0],line[1],line[2],line[3],line[4])
                    values.update({
                        'default_code': line[0],
                        'mgo_code' : str(int(float(line[1]))) if line[1] else '',
                        'lot': line[2],
                        'expiry_date':expiry_date_string,
                        'quantity': line[4],
                        'picking_type_id': self.picking_type_id.id,
                        'location_id': self.location_id.id,
                        'location_dest_id': self.location_dest_id.id,
                        'seq' : self.seq,
                    })

                    self.create_picking(values)
