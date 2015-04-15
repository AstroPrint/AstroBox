# coding=utf-8
__author__ = "Daniel Arroyo. 3DaGogo, Inc <daniel@astroprint.com>"
__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from astroprint.printer.manager import printerManager
from astroprint.printfiles.map import SUPPORTED_EXTENSIONS

from watchdog.events import PatternMatchingEventHandler

class UploadCleanupWatchdogHandler(PatternMatchingEventHandler):
	"""
	Takes care of automatically deleting metadata entries for files that get deleted from the uploads folder
	"""

	patterns = map(lambda x: "*.%s" % x, SUPPORTED_EXTENSIONS)

	def __init__(self):
		PatternMatchingEventHandler.__init__(self)

	def on_deleted(self, event):
		fm = printerManager().fileManager
		filename = fm._getBasicFilename(event.src_path)
		if not filename:
			return

		fm.removeFileFromMetadata(filename)