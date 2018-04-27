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
			self._logger.info("No Utilities menu present: A new one was loaded in memory.")
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
			]

			return

	def save(self):
		with open(self._maintenanceMenu, "wb") as maintenanceMenu:
			yaml.safe_dump(self.data, maintenanceMenu, default_flow_style=False, indent="    ", allow_unicode=True)

	def fileExists(self):
		return len(self.data)

	def checkMenuFile(self, file):
		filename = file.filename

		if not ('.' in filename and filename.rsplit('.', 1)[1].lower() in ['zip']):
			return {'error':'invalid_file'}

		savedFile = os.path.join(gettempdir(), secure_filename(file.filename))
		try:
			file.save(savedFile)
			zip_ref = zipfile.ZipFile(savedFile, 'r')
			menuInfo = zip_ref.open('utilities-menu.yaml', 'r')
			definition = yaml.safe_load(menuInfo)

		except KeyError:
			zip_ref.close()
			os.unlink(savedFile)
			return {'error':'invalid_menu_file'}

		except:
			zip_ref.close()
			os.unlink(savedFile)

			self._logger.error('Error checking uploaded Zip file', exc_info=True)
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
			configDir = settings().getConfigFolder()

			#extract the contents of the plugin in it's directory
			zip_ref = zipfile.ZipFile(filename, 'r')
			menuInfo = zip_ref.open('utilities-menu.yaml', 'r')
			definition = yaml.safe_load(menuInfo)
			assetsDir = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)),'static','img','utilities_menu'))

			#remove utilities_menu folder
			shutil.rmtree(assetsDir, ignore_errors=True)

			#move the image files into utilities_menu folder
			for file in zip_ref.namelist():
				if file.startswith('assets/'):
					fileIcon = file.replace('assets/','')
					if fileIcon:
						zip_ref.extract(file, assetsDir)
						os.rename(os.path.join(assetsDir, file), os.path.join(assetsDir, file.replace('assets/','')))

				if os.path.isdir(os.path.join(assetsDir, 'assets')):
					os.rmdir(os.path.join(assetsDir, 'assets'))

			zip_ref.extract('utilities-menu.yaml', configDir)
			#rename the yaml file
			os.rename(os.path.join(configDir,'utilities-menu.yaml'), os.path.join(configDir, "utilities-menu.yaml"))
			zip_ref.close()

			self.data = definition
			return True

		return False

	def removeMenu(self, tId):

		configFolder = settings().getConfigFolder()

		#remove definition file
		os.remove(os.path.join(configFolder, "utilities-menu.yaml"))

		self._logger.info("Menu Removed")

		return {'removed Menu'}


