# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

# singleton
_instance = None

# This object is recreated when the driver is changed in the printer profile page.
# DO NOT store a reference to the result of printerManager in any persistant object.

def printerManager(driver = None):
	global _instance

	if driver is not None and _instance is not None and _instance.driverName != driver:
		_instance.rampdown()
		_instance = None

	if _instance is None:
		from .marlin import PrinterMarlin
		from .s3g import PrinterS3g
		from .virtual import PrinterVirtual

		_instance = {
			PrinterMarlin.driverName: PrinterMarlin,
			PrinterS3g.driverName: PrinterS3g,
			PrinterVirtual.driverName: PrinterVirtual
		}[driver]()

	return _instance
