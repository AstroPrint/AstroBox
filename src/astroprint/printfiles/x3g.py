__author__ = "Daniel Arroyo. 3DaGogo, Inc <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

from octoprint.events import eventManager, Events

from astroprint.printfiles import PrintFilesManager, MetadataAnalyzer

class PrintFileManagerX3g(PrintFilesManager):
	name = 'x3g'
	SUPPORTED_EXTENSIONS = ["x3g"]

	def __init__(self):
		self._logger = logging.getLogger(__name__)

		super(PrintFileManagerX3g, self).__init__()

		self._metadataAnalyzer = X3gMetadataAnalyzer(getPathCallback=self.getAbsolutePath, loadedCallback=self._onMetadataAnalysisFinished)

class X3gMetadataAnalyzer(MetadataAnalyzer):
	def __init__(self, getPathCallback, loadedCallback):
		self._logger = logging.getLogger(__name__)
		super(X3gMetadataAnalyzer, self).__init__(getPathCallback, loadedCallback)

	def _analyzeFile(self, filename):
		path = self._getPathCallback(filename)
		if path is None or not os.path.exists(path):
			return

		self._currentFile = filename
		self._currentProgress = 0

		try:
			self._logger.debug("Starting analysis of file %s" % filename)
			eventManager().fire(Events.METADATA_ANALYSIS_STARTED, {"file": filename})
			#self._gcode = gcodeInterpreter.gcode()
			#self._gcode.progressCallback = self._onParsingProgress
			#self._gcode.load(path)
			self._logger.debug("Analysis of file %s finished, notifying callback" % filename)
			self._loadedCallback(self._currentFile, self._gcode)
		finally:
			#self._gcode = None
			self._currentProgress = None
			self._currentFile = None

	def _onParsingProgress(self, progress):
		self._currentProgress = progress