# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2019 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import os

from octoprint.settings import settings

# singleton
_instance = None

def platformManager():
	global _instance
	if _instance is None:
		_instance = PlatformManager()
	return _instance

class PlatformManager(object):
	def listLogs(self):
		s = settings()

		logsDir = s.getBaseFolder("logs")

		return [{'name': f, 'size': os.path.getsize(os.path.join(logsDir, f))} for f in os.listdir(logsDir)]

	def logsSize(self):
		s = settings()

		logsDir = s.getBaseFolder("logs")
		return sum([os.path.getsize(os.path.join(logsDir, f)) for f in os.listdir(logsDir)])

	def uploadsSize(self):
		s = settings()

		uploadsDir = s.getBaseFolder("uploads")
		return sum([os.path.getsize(os.path.join(uploadsDir, f)) for f in os.listdir(uploadsDir)])

	def driveStats(self):
		st = os.statvfs("/")
		free = st.f_bavail * st.f_frsize
		total = st.f_blocks * st.f_frsize
		used = (st.f_blocks - st.f_bfree) * st.f_frsize

		return total, used, free
