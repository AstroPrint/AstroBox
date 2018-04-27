# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2018 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

# singleton
_instance = None

def maintenanceMenuManager():
	global _instance
	if _instance is None:
		_instance = MaintenanceMenuManager()
	return _instance

import yaml
import os
import logging
import glob
import zipfile
import shutil

from werkzeug.utils import secure_filename
from tempfile import gettempdir

from octoprint.settings import settings

class MaintenanceMenuManager(object):

	def __init__(self):
		self._settings = settings()
		self._logger = logging.getLogger(__name__)
		self.data = []

		self._logger.info("Loading Maintenance Menu...")

		configDir = self._settings.getConfigFolder()

		self._maintenanceMenu = "%s/utilities-menu.yaml" % configDir

		if os.path.isfile(self._maintenanceMenu):
			config = None
			self._logger.info("Found maintenance menu to load.")
			try:
				with open(self._maintenanceMenu, "r") as f:
					config = yaml.safe_load(f)
					if config:
						self.data = config

			except:
				self._logger.info("There was an error loading %s:" % f, exc_info= True)

			return
		else:
			self._logger.info("No Utilities menu present: A new one was created.")
			self.data = [
				{
					'id' : "movements_controls",
					'name' : {
						'en': "Movement Controls",
						'es': "Controles y movimiento"
					},
					'type' : "utility",
					'hiddenOnPrinting' : True
				},
				{
					'id' : "preheat",
					'name' : {
						'en': "Pre Heat",
						'es': "Pre Calentar"
					},
					'type' : "utility"
				},
					{
					'id' : "fan",
					'name' : {
						'en': "Fan",
						'es': "Ventiladores"
					},
					'type' : "utility"
				},
				{
					'id' : "filament_extruder",
					'name' : {
						'en': "Filament Extruder",
						'es': "Extrusión Filamento"
					},
					'type' : "utility",
					'hiddenOnPrinting' : True
				},
				{
					'id' : "tasks",
					'name' : {
						'en': "Tasks",
						'es': "Tareas"
					},
					'type' : "utility",
					'hiddenOnPrinting' : True
				},{
					'id' : "printing_speed",
					'name' : {
						'en': "Printing Speed",
						'es': "Velocidad Impresión"
					},
					'type' : "utility"
				}
				# the following are only for testing porpuses
				,{
					'id' : "leveling_relia5000",
					'name' : {
						'en': "Bed Leveling",
						'es': "Nivelar cama"
					},
					'type' : "task",
					'hiddenOnPrinting' : True,
					'hiddenOnPause' : True
				},
				{
					'id' : "menu_filament",
					'name' : {
						'en': "Filament Tools",
						'es': "Herramientas filamento"
					},
					'type' : "menu",
					'hiddenOnPrinting' : True,
					'hiddenOnPause' : True,
					'menu': 	[
						{
							'name' : {
								'en': "Change",
								'es': "Cambiar"
							},
							'type' : "menu",
							'menu': [
								{
									'id' : "load_wanhaoi3",
									'name' : {
										'en': "Load",
										'es': "Cargar"
									},
									'type' : "task"
								},
								{
									'id' : "load_relia5000",
									'name' : {
										'en': "Unload",
										'es': "Descargar"
									},
									'type' : "task"
								}
							]
						}
					]
				}
			]
			open(self._maintenanceMenu, 'w').close()

			if self._maintenanceMenu:
				config = None
				with open(self._maintenanceMenu, "r") as f:
					config = yaml.safe_load(f)

				def merge_dict(a,b):
					for key in b:
						if isinstance(b[key], dict):
							merge_dict(a[key], b[key])
						else:
							a[key] = b[key]

				if config:
					merge_dict(self.data, config)

			self.save()

			return

	def save(self):
		with open(self._maintenanceMenu, "wb") as maintenanceMenu:
			yaml.safe_dump(self.data, maintenanceMenu, default_flow_style=False, indent="    ", allow_unicode=True)

	def fileExists(self):
		return len(self.data)

	def checkMenuFile(self, file):
		filename = file.filename

		if not ('.' in filename and filename.rsplit('.', 1)[1].lower() in ['yaml']):
			return {'error':'invalid_file'}

		savedFile = os.path.join(gettempdir(), secure_filename(file.filename))
		try:
			file.save(savedFile)

			with open(savedFile, "r") as f:
				definition = yaml.safe_load(f)

		except KeyError:
			os.unlink(savedFile)
			return {'error':'invalid_menu_file'}

		except:
			os.unlink(savedFile)

			self._logger.error('Error checking uploaded Yaml file', exc_info=True)
			return {'error':'error_checking_file'}

		#Check if the min_api_version is valid
		#min_api_version = int(definition['min_api_version'])
		#if TASK_API_VERSION < min_api_version:
		#	os.unlink(savedFile)
		#	return {'error':'incompatible_task', 'api_version': min_api_version}
		response = {
			'tmp_file': savedFile,
			'definition': definition
		}

		return response

	def installFile(self, filename):
		if os.path.isfile(filename):

			configFolder = settings().getConfigFolder()

			#get  yaml file content from tmp directory
			with open(filename, "r") as f:
				definition = yaml.safe_load(f)

			#copy yaml content in config directory
			os.rename(filename, os.path.join(configFolder, "utilities-menu.yaml"))

			self.data = definition
			return True

		return False

	def removeMenu(self, tId):

		configFolder = settings().getConfigFolder()

		#remove definition file
		os.remove(os.path.join(configFolder, "utilities-menu.yaml"))

		self._logger.info("Menu Removed")

		return {'removed Menu'}


