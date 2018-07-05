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
			'variant': {
				'printer_profile_edit': True,
				'allow_camera_settings': True,
				'additional_custom_tasks': True,
				'allow_menu_upload': True,
				'change_update_channel': True,
				'logo': None,
				'shutdown_img': None,
				'product_name': 'AstroBox',
				'network_name': 'astrobox'
			},
			'links': {
				'support': '#help',
				'supplies': '#supplies',
				'product': 'https://www.astroprint.com/products/p/astrobox'
			},
			'strings': {
				'welcome_header': None,
				'welcome_content': None,
				'setup_done': None,
				'shutdown_message': None
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
			'printer_connection': {
				'baudrate': None,
				'port': None
			}
		}
		self._settings = settings()
		self._logger = logging.getLogger(__name__)
		self._folder = self._settings.get(['folder', 'manufacturerPkg']) or ( '%sAstroBox-Manufacturer' % os.sep )
		self._loadDefinition()

	@property
	def variant(self):
		return self.data['variant']

	@property
	def printerProfile(self):
		return self.data['printer_profile']

	@property
	def printerConnection(self):
		return self.data['printer_connection']

	@property
	def links(self):
		return self.data['links']

	@property
	def certFilePath(self):
		if os.path.isfile(os.path.join(self._folder, 'certificate.pem')):
			return os.path.join(self._folder, 'certificate.pem')
		else:
			return os.path.join(os.path.dirname(self._settings._configfile), 'certificate.pem')

	def getString(self, strId, lang):
		string = self.data['strings'].get(strId)
		if string:
			return string.get(lang) or string.get('en')

		return None

	def _loadDefinition(self, ):
		if os.path.isdir(self._folder):
			def_file = os.path.join(self._folder, 'definition.yaml')

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
