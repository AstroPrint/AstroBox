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

def printerManager(driver, fileManager = None):
	global _instance
	if _instance is None:
		_instance = printerDriverMap[driver](fileManager)

	elif _instance.driverName != driver:
		_instance.disconnect()
		_instance = printerDriverMap[driver](fileManager or _instance._gcodeManager )

	return _instance