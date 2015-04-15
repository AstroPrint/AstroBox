__author__ = "Daniel Arroyo. 3DaGogo, Inc <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import os

from octoprint.events import eventManager, Events

from astroprint.printfiles import PrintFilesManager, MetadataAnalyzer, MetadataAnalyzerResults

class PrintFileManagerX3g(PrintFilesManager):
	name = 'x3g'
	fileFormat = 'x3g'
	SUPPORTED_EXTENSIONS = ["x3g"]

	def __init__(self):
		self._logger = logging.getLogger(__name__)
		self._metadataAnalyzer = X3gMetadataAnalyzer(getPathCallback=self.getAbsolutePath, loadedCallback=self._onMetadataAnalysisFinished)
		super(PrintFileManagerX3g, self).__init__()

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
			self._logger.debug("Analysis of file %s finished, notifying callback" % filename)
			self._loadedCallback(self._currentFile, MetadataAnalyzerResults())
		finally:
			self._currentProgress = None
			self._currentFile = None
