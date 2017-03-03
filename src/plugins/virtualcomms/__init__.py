# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from astroprint.plugin import Plugin, PrinterCommsService

class VirtualComms(Plugin, PrinterCommsService):

	# PrinterCommsService
	@property
	def driverName(self):
		return ('virtual', "Virtual Printer")

__plugin_instance__ = VirtualComms()
