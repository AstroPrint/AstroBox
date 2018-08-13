__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2018 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from sys import platform

# singleton
_instance = None

def externalDriveManager():
	global _instance

	if _instance is None:
		if platform.startswith("linux"):
			from .linux import ExternalDriveManager
			_instance = ExternalDriveManager()

		elif platform == "darwin":
			from .mac_dev import ExternalDriveManager
			_instance = ExternalDriveManager()

	return _instance
