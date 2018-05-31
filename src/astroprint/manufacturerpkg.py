# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2018 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

# singleton
_instance = None

def manufacturerPkgManager():
	global _instance
	if _instance is None:
		_instance = ManufacturerPkgManager()
	return _instance

import logging
import yaml
import os

from octoprint.settings import settings
from astroprint.util import merge_dict

class ManufacturerPkgManager(object):
	def __init__(self):
		self.data = {
			'customization': {
				'printer_profile_edit': True,
				'allow_camera_settings': True,
				'additional_custom_tasks': True,
				'allow_menu_upload': True,
				'logo': 'astrobox_logo_medium.png'
			},
			'printer_profile': {
				'driver': None,
				'extruder_count': None,
				'max_nozzle_temp': None,
				'max_bed_temp': None,
				'heated_bed': None,
				'cancel_gcode': None,
				'invert_z': None,
				'invert_x': None,
				'invert_y': None,
				'temp_presets' : None
			},
			'printer_connection':{
				'baudrate': None,
				'port': None
			}
		}
		self.settings = settings()
		self._logger = logging.getLogger(__name__)
		self._loadDefinition( self.settings.get(['folder', 'manufacturerPkg']) or ( '%sAstroBox-Manufacturer' % os.sep ) )

	@property
	def customization(self):
		return self.data['customization']

	@property
	def printerProfile(self):
		return self.data['printer_profile']

	@property
	def printerConnection(self):
		return self.data['printer_connection']

	def _loadDefinition(self, folder):
		if os.path.isdir(folder):
			def_file = os.path.join(folder, 'definition.yaml')

			if os.path.isfile(def_file):
				try:
					with open(def_file, "r") as f:
						definition = yaml.safe_load(f)

					if definition:
						self._logger.info("Manufacturer definition loaded.")
						merge_dict(self.data, definition)

				except:
					self._logger.error("There was an error loading %s:" % def_file, exc_info= True)

				return

		self._logger.info('No Manufacturer Package present')
