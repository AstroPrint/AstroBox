# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from astroprint.printer.marlin import PrinterMarlin
from astroprint.printer.s3g import PrinterS3g

# singleton
_instance = None

printerDriverMap = {
	PrinterMarlin.driverName: PrinterMarlin,
	PrinterS3g.driverName: PrinterS3g
}

# This object is recreated when the driver is changed in the printer profile page.
# DO NOT store a reference to the result of printerManager in any persistant object.

def printerManager(driver = None):
	global _instance
	if _instance is None:
		_instance = printerDriverMap[driver]()

	elif driver is not None and _instance.driverName != driver:
		_instance.rampdown()
		_instance = printerDriverMap[driver]()

	return _instance