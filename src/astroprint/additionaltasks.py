# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2018 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

# singleton
_instance = None

def additionalTasksManager():
	global _instance
	if _instance is None:
		_instance = AdditionalTasksManager()
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

class AdditionalTasksManager(object):
	REQUIRED_TASK_KEYS = ['id', 'steps']

	def __init__(self):
		self._settings = settings()
		self._logger = logging.getLogger(__name__)
		self.data = []

		self._logger.info("Loading Additional Tasks...")

		tasksDir = self._settings.getBaseFolder('tasks')
		#tasksDir = "%s/tasks" % self._settings.getConfigFolder()

		if os.path.isdir(tasksDir):
			taskFiles = glob.glob('%s/*.yaml' % tasksDir)
			if len(taskFiles):
				self._logger.info("Found %d tasks to load." % len(taskFiles))
				for f in taskFiles:
					try:
						with open(f, "r") as f:
							config = yaml.safe_load(f)
							if config:
								self.data.append(config)

					except:
						self._logger.info("There was an error loading %s:" % f, exc_info= True)

				return

		self._logger.info("No additional Tasks present.")

	def getTask(self, id):
		for task in self.data:
			if task['id'] == id:
				return task

		return None

	def checkTaskFile(self, file):
		filename = file.filename

		if not ('.' in filename and filename.rsplit('.', 1)[1].lower() in ['zip']):
			return {'error':'invalid_file'}

		savedFile = os.path.join(gettempdir(), secure_filename(file.filename))
		try:
			file.save(savedFile)
			zip_ref = zipfile.ZipFile(savedFile, 'r')
			taskInfo = zip_ref.open('task.yaml', 'r')
			definition = yaml.safe_load(taskInfo)

		except KeyError:
			zip_ref.close()
			os.unlink(savedFile)
			return {'error':'invalid_task_file'}

		except:
			zip_ref.close()
			os.unlink(savedFile)
			self._logger.error('Error checking uploaded Zip file', exc_info=True)
			return {'error':'error_checking_file'}

		zip_ref.close()

		if not all(key in definition for key in self.REQUIRED_TASK_KEYS):
			os.unlink(savedFile)
			return {'error':'invalid_task_definition'}

		#Check if the min_api_version is valid
		#min_api_version = int(definition['min_api_version'])
		#if TASK_API_VERSION < min_api_version:
		#	os.unlink(savedFile)
		#	return {'error':'incompatible_task', 'api_version': min_api_version}

		task = self.getTask(definition['id'])
		if task:
			os.unlink(savedFile)
			return {'error':'already_installed'}

		response = {
			'tmp_file': savedFile,
			'definition': definition
		}

		return response

	def installFile(self, filename):
		if os.path.isfile(filename):
			tasksDir = settings().getBaseFolder('tasks')

			#extract the contents of the plugin in it's directory
			zip_ref = zipfile.ZipFile(filename, 'r')
			taskInfo = zip_ref.open('task.yaml', 'r')
			definition = yaml.safe_load(taskInfo)

			taskId = definition.get('id')
			if taskId:
				assetsDir = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)),'static','img','variant', taskId))
				for file in zip_ref.namelist():
					if file.startswith('assets/'):
						filename = file.replace('assets/','')
						if filename:
							zip_ref.extract(file, assetsDir)
							os.rename(os.path.join(assetsDir, file), os.path.join(assetsDir, file.replace('assets/','')))

					if os.path.isdir(os.path.join(assetsDir, 'assets')):
						os.rmdir(os.path.join(assetsDir, 'assets'))

				zip_ref.extract('task.yaml',tasksDir)
				#rename the yaml file
				os.rename(os.path.join(tasksDir,'task.yaml'), os.path.join(tasksDir, "%s.yaml" % taskId))
				zip_ref.close()

				self.data.append(definition)
				return True

			zip_ref.close()

		return False

	def removeTask(self, tId):
		task = self.getTask(tId)

		if task:
			for t in self.data:
				if t['id'] == tId:
					self.data.remove(t)
					break

			tasksDir = settings().getBaseFolder('tasks')

			#remove definition file
			os.remove(os.path.join(tasksDir, "%s.yaml" % tId))
			#remove asset dir
			shutil.rmtree( os.path.join(os.path.dirname(os.path.realpath(__file__)),'static','img','variant', tId) )

			self._logger.info("Task [%s] Removed" % tId)

			return {'removed': tId}

		else:
			return {'error': 'not_found'}
