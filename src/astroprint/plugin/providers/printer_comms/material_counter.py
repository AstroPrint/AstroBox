__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2016 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import logging

from copy import copy

class MaterialCounter(object):
	#Extrusion modes
	EXTRUSION_MODE_ABSOLUTE = 1
	EXTRUSION_MODE_RELATIVE = 2

	def __init__(self):
		self._logger = logging.getLogger(__name__)
		self._extrusionMode = self.EXTRUSION_MODE_ABSOLUTE
		self._activeTool = "0";
		self._lastExtruderLengthReset = {"0": 0}
		self._consumedFilament = {"0": 0}
		self._lastExtrusion = {"0": 0}

	def startPrint(self):
		tool = self._activeTool

		self._lastExtruderLengthReset = {tool: 0}
		self._consumedFilament = {tool: 0}
		self._lastExtrusion = {tool: 0}

	@property
	def extrusionMode(self):
		return self._extrusionMode

	@property
	def consumedFilament(self):
		if self._consumedFilament and self._extrusionMode == self.EXTRUSION_MODE_ABSOLUTE:
			tool = self._activeTool
			consumedFilament = copy(self._consumedFilament)

			try:
				consumedFilament[tool] += ( self._lastExtrusion[tool] - self._lastExtruderLengthReset[tool] )

			except KeyError:
				return None

			return consumedFilament

		else:
			return self._consumedFilament

	@property
	def totalConsumedFilament(self):
		consumedFilament = self.consumedFilament
		return sum([consumedFilament[k] for k in consumedFilament.keys()])

	def changeActiveTool(self, newTool, oldTool):
		#Make sure the head is registered
		if newTool not in self._consumedFilament:
			self._consumedFilament[newTool] = 0
			self._lastExtruderLengthReset[newTool] = 0
			self._lastExtrusion[newTool] = 0

		if self._extrusionMode == self.EXTRUSION_MODE_ABSOLUTE:
			if oldTool in self.consumedFilament and oldTool in self._lastExtrusion and oldTool in self._lastExtruderLengthReset:
				self.consumedFilament[oldTool] += ( self._lastExtrusion[oldTool] - self._lastExtruderLengthReset[oldTool] )
				self._lastExtruderLengthReset[oldTool] = self.consumedFilament[oldTool]
			else:
				self._logger.error('Unkonwn previous tool %s when trying to change to new tool %s' % (oldTool, newTool))

		self._activeTool = newTool

	def changeExtrusionMode(self, mode):
		self._extrusionMode = mode

		if mode == self.EXTRUSION_MODE_RELATIVE:
			tool = self._activeTool

			#it was absolute before so we add what we had to the active head counter
			self._consumedFilament[tool] += ( self._lastExtrusion[tool] - self._lastExtruderLengthReset[tool] )

	def resetExtruderLength(self, newLength):
		tool = self._activeTool

		if self._extrusionMode == self.EXTRUSION_MODE_ABSOLUTE:
			# We add what we have to the total for the his tool head
			self._consumedFilament[tool] += ( self._lastExtrusion[tool] - self._lastExtruderLengthReset[tool] )

		self._lastExtruderLengthReset[tool] = newLength
		self._lastExtrusion[tool] = newLength

	def reportExtrusion(self, length):
		if self._extrusionMode == self.EXTRUSION_MODE_RELATIVE:
			if length > 0: #never report retractions
				self._consumedFilament[self._activeTool] += length

		else: # EXTRUSION_MODE_ABSOLUTE
			tool = self._activeTool

			if length > self._lastExtrusion[tool]: #never report retractions
				self._lastExtrusion[tool] = length
