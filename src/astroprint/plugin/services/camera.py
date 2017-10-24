# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from . import PluginService
from octoprint.events import Events
from astroprint.camera import cameraManager

class CameraService(PluginService):
	_validEvents = []

	def __init__(self):
		super(CameraService, self).__init__()

	#REQUESTS

	def getPhoto(self, doneWithPhoto):
		cameraManager().get_pic_async(doneWithPhoto)
