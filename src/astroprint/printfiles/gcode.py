# coding=utf-8
from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net> based on work by David Braam"
__author__ = "Daniel Arroyo. 3DaGogo, Inc <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import os
import logging
import math
import base64
import zlib

from octoprint.settings import settings

from octoprint.events import eventManager, Events

from astroprint.printfiles import PrintFilesManager, MetadataAnalyzer, FileDestinations, AnalysisAborted

class PrintFileManagerGcode(PrintFilesManager):
	name = 'gcode'
	fileFormat = 'gcode'
	SUPPORTED_EXTENSIONS = ["gcode", "gco", "g"]

	def __init__(self):
		self._logger = logging.getLogger(__name__)
		self._metadataAnalyzer = GcodeMetadataAnalyzer(getPathCallback=self.getAbsolutePath, loadedCallback=self._onMetadataAnalysisFinished)
		super(PrintFileManagerGcode, self).__init__()

class GcodeMetadataAnalyzer(MetadataAnalyzer):
	def __init__(self, getPathCallback, loadedCallback):
		self._logger = logging.getLogger(__name__)

		self._gcode = None

		super(GcodeMetadataAnalyzer, self).__init__(getPathCallback, loadedCallback)

	def pause(self):
		super(GcodeMetadataAnalyzer, self).pause()
		
		if self._gcode is not None:
			self._logger.debug("Aborting running analysis, will restart when Gcode analyzer is resumed")
			self._gcode.abort()

	def _analyzeFile(self, filename):
		path = self._getPathCallback(filename)
		if path is None or not os.path.exists(path):
			return

		self._currentFile = filename
		self._currentProgress = 0

		try:
			self._logger.debug("Starting analysis of file %s" % filename)
			eventManager().fire(Events.METADATA_ANALYSIS_STARTED, {"file": filename})
			self._gcode = GcodeInterpreter()
			self._gcode.progressCallback = self._onParsingProgress
			self._gcode.load(path)
			self._logger.debug("Analysis of file %s finished, notifying callback" % filename)
			self._loadedCallback(self._currentFile, self._gcode)

		finally:
			self._gcode = None
			self._currentProgress = None
			self._currentFile = None

class GcodeInterpreter(object):
	def __init__(self):
		self._logger = logging.getLogger(__name__)

		self.layerList = None
		self.extrusionAmount = [0]
		self.extrusionVolume = [0]
		self.totalMoveTimeMinute = 0
		self.filename = None
		self.progressCallback = None
		self._abort = False
		self._filamentDiameter = 0
	
	def load(self, filename):
		if os.path.isfile(filename):
			self.filename = filename
			self._fileSize = os.stat(filename).st_size
			with open(filename, "r") as f:
				self._load(f)

	def abort(self):
		self._abort = True

	def _load(self, gcodeFile):
		filePos = 0
		pos = [0.0, 0.0, 0.0]
		posOffset = [0.0, 0.0, 0.0]
		currentE = [0.0]
		totalExtrusion = [0.0]
		maxExtrusion = [0.0]
		currentExtruder = 0
		totalMoveTimeMinute = 0.0
		absoluteE = True
		scale = 1.0
		posAbs = True
		feedRateXY = settings().getFloat(["printerParameters", "movementSpeed", "x"])
		offsets = settings().get(["printerParameters", "extruderOffsets"])

		for line in gcodeFile:
			if self._abort:
				raise AnalysisAborted()
			filePos += 1

			try:
				if self.progressCallback is not None and (filePos % 1000 == 0):
					if isinstance(gcodeFile, (file)):
						self.progressCallback(float(gcodeFile.tell()) / float(self._fileSize))
					elif isinstance(gcodeFile, (list)):
						self.progressCallback(float(filePos) / float(len(gcodeFile)))
			except:
				pass

			if ';' in line:
				comment = line[line.find(';')+1:].strip()
				if comment.startswith("filament_diameter"):
					self._filamentDiameter = float(comment.split("=", 1)[1].strip())
				elif comment.startswith("CURA_PROFILE_STRING"):
					curaOptions = self._parseCuraProfileString(comment)
					if "filament_diameter" in curaOptions:
						try:
							self._filamentDiameter = float(curaOptions["filament_diameter"])
						except:
							self._filamentDiameter = 0.0
				line = line[0:line.find(';')]

			G = self._getCodeInt(line, 'G')
			M = self._getCodeInt(line, 'M')
			T = self._getCodeInt(line, 'T')

			if G is not None:
				if G == 0 or G == 1:	#Move
					x = self._getCodeFloat(line, 'X')
					y = self._getCodeFloat(line, 'Y')
					z = self._getCodeFloat(line, 'Z')
					e = self._getCodeFloat(line, 'E')
					f = self._getCodeFloat(line, 'F')
					oldPos = pos
					pos = pos[:]
					if posAbs:
						if x is not None:
							pos[0] = x * scale + posOffset[0]
						if y is not None:
							pos[1] = y * scale + posOffset[1]
						if z is not None:
							pos[2] = z * scale + posOffset[2]
					else:
						if x is not None:
							pos[0] += x * scale
						if y is not None:
							pos[1] += y * scale
						if z is not None:
							pos[2] += z * scale
					if f is not None:
						feedRateXY = f

					moveType = 'move'
					if e is not None:
						if absoluteE:
							e -= currentE[currentExtruder]
						if e > 0.0:
							moveType = 'extrude'
						if e < 0.0:
							moveType = 'retract'
						totalExtrusion[currentExtruder] += e
						currentE[currentExtruder] += e
						if totalExtrusion[currentExtruder] > maxExtrusion[currentExtruder]:
							maxExtrusion[currentExtruder] = totalExtrusion[currentExtruder]
					else:
						e = 0.0

					if x is not None or y is not None or z is not None:
						diffX = oldPos[0] - pos[0]
						diffY = oldPos[1] - pos[1]
						totalMoveTimeMinute += math.sqrt(diffX * diffX + diffY * diffY) / feedRateXY
					elif moveType == "extrude":
						diffX = oldPos[0] - pos[0]
						diffY = oldPos[1] - pos[1]
						time1 = math.sqrt(diffX * diffX + diffY * diffY) / feedRateXY
						time2 = abs(e / feedRateXY)
						totalMoveTimeMinute += max(time1, time2)
					elif moveType == "retract":
						totalMoveTimeMinute += abs(e / feedRateXY)

					if moveType == 'move' and oldPos[2] != pos[2]:
						if oldPos[2] > pos[2] and abs(oldPos[2] - pos[2]) > 5.0 and pos[2] < 1.0:
							oldPos[2] = 0.0
				elif G == 4:	#Delay
					S = self._getCodeFloat(line, 'S')
					if S is not None:
						totalMoveTimeMinute += S / 60.0
					P = self._getCodeFloat(line, 'P')
					if P is not None:
						totalMoveTimeMinute += P / 60.0 / 1000.0
				elif G == 20:	#Units are inches
					scale = 25.4
				elif G == 21:	#Units are mm
					scale = 1.0
				elif G == 28:	#Home
					x = self._getCodeFloat(line, 'X')
					y = self._getCodeFloat(line, 'Y')
					z = self._getCodeFloat(line, 'Z')
					center = [0.0,0.0,0.0]
					if x is None and y is None and z is None:
						pos = center
					else:
						pos = pos[:]
						if x is not None:
							pos[0] = center[0]
						if y is not None:
							pos[1] = center[1]
						if z is not None:
							pos[2] = center[2]
				elif G == 90:	#Absolute position
					posAbs = True
				elif G == 91:	#Relative position
					posAbs = False
				elif G == 92:
					x = self._getCodeFloat(line, 'X')
					y = self._getCodeFloat(line, 'Y')
					z = self._getCodeFloat(line, 'Z')
					e = self._getCodeFloat(line, 'E')
					if e is not None:
						currentE[currentExtruder] = e
					if x is not None:
						posOffset[0] = pos[0] - x
					if y is not None:
						posOffset[1] = pos[1] - y
					if z is not None:
						posOffset[2] = pos[2] - z

			elif M is not None:
				if M == 82:   #Absolute E
					absoluteE = True
				elif M == 83:   #Relative E
					absoluteE = False

			elif T is not None:
				posOffset[0] -= offsets[currentExtruder]["x"] if currentExtruder < len(offsets) else 0
				posOffset[1] -= offsets[currentExtruder]["y"] if currentExtruder < len(offsets) else 0

				currentExtruder = T

				posOffset[0] += offsets[currentExtruder]["x"] if currentExtruder < len(offsets) else 0
				posOffset[1] += offsets[currentExtruder]["y"] if currentExtruder < len(offsets) else 0

				if len(currentE) <= currentExtruder:
					for i in range(len(currentE), currentExtruder + 1):
						currentE.append(0.0)
				if len(maxExtrusion) <= currentExtruder:
					for i in range(len(maxExtrusion), currentExtruder + 1):
						maxExtrusion.append(0.0)
				if len(totalExtrusion) <= currentExtruder:
					for i in range(len(totalExtrusion), currentExtruder + 1):
						totalExtrusion.append(0.0)

		if self.progressCallback is not None:
			self.progressCallback(100.0)

		self.extrusionAmount = maxExtrusion
		self.extrusionVolume = [0] * len(maxExtrusion)
		for i in range(len(maxExtrusion)):
			radius = self._filamentDiameter / 2
			self.extrusionVolume[i] = (self.extrusionAmount[i] * (math.pi * radius * radius)) / 1000
		self.totalMoveTimeMinute = totalMoveTimeMinute

	def _parseCuraProfileString(self, comment):
		return {key: value for (key, value) in map(lambda x: x.split("=", 1), zlib.decompress(base64.b64decode(comment[len("CURA_PROFILE_STRING:"):])).split("\b"))}

	def _getCodeInt(self, line, code):
		n = line.find(code) + 1
		if n < 1:
			return None
		m = line.find(' ', n)
		try:
			if m < 0:
				return int(line[n:])
			return int(line[n:m])
		except:
			return None

	def _getCodeFloat(self, line, code):
		n = line.find(code) + 1
		if n < 1:
			return None
		m = line.find(' ', n)
		try:
			if m < 0:
				return float(line[n:])
			return float(line[n:m])
		except:
			return None

