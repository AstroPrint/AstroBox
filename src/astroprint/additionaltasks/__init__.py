# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

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

from octoprint.settings import settings

class AdditionalTasksManager(object):
	def __init__(self):
		self._settings = settings()
		self._logger = logging.getLogger(__name__)
		self.data = {}

		self._logger.info("Loading Additional Tasks...")

		tasksDir = "%s/tasks" % self._settings.getConfigFolder()

		if os.path.isdir(tasksDir):
			taskFiles = glob.glob('%s/*.yaml' % tasksDir)
			if len(taskFiles):
				self._logger.info("Found %d tasks to load." % len(taskFiles))
				for f in taskFiles:
					try:
						with open(f, "r") as f:
							config = yaml.safe_load(f)
							if config:
								self.data[config['id']] = config

					except:
						self._logger.info("There was an error loading %s:" % f, exc_info= True)

				return

		self._logger.info("No additional Tasks present.")
