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

		maintenanceMenu = "%s/maintenance-menu.yaml" % configDir

		if os.path.isfile(maintenanceMenu):
			config = None
			self._logger.info("Found maintenance menu to load.")
			try:
				with open(maintenanceMenu, "r") as f:
					config = yaml.safe_load(f)
					if config:
						self.data = config

			except:
				self._logger.info("There was an error loading %s:" % f, exc_info= True)

			return

		self._logger.info("No Maintenance menu present")


	def fileExists(self):
		return len(self.data)

	def checkTaskFile(self, file):
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

			#extract the yaml file in it's directory
			with open(filename, "r") as f:
				definition = yaml.safe_load(f)

			#rename the yaml file
			os.rename(filename, os.path.join(configFolder, "maintenance-menu.yaml"))

			self.data = definition
			return True

		return False

	def removeMenu(self, tId):

		configFolder = settings().getConfigFolder()

		#remove definition file
		os.remove(os.path.join(configFolder, "maintenance-menu.yaml"))

		self._logger.info("Menu Removed")

		return {'removed Menu'}


