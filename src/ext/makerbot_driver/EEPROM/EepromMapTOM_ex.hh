/*
 * Copyright 2010 by Adam Mayer	 <adam@makerbot.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>
 */

#ifndef EEPROM_MAP_HH_
#define EEPROM_MAP_HH_

#include <stdint.h>
#include "Thermistor.hh"

/// Describe the EEPROM map.
/// Why are we not describing this as a packed struct?  Because the
/// information needs to be shared with external applications (currently
/// java, etc.

namespace eeprom {

const static uint16_t EEPROM_SIZE				= 0x0200;

//// Start of map
//// Uninitialized memory is 0xff.  0xff should never
//// be used as a valid value for initialized memory!

/// Version, low byte: 1 byte
const static uint16_t VERSION_LOW				= 0x0000;
/// Version, high byte: 1 byte
const static uint16_t VERSION_HIGH				= 0x0001;

//// Feature map: 2 bytes
const static uint16_t FEATURES					= 0x0002;
enum {
	HEATER_0_PRESENT		= 1 << 0,
	HEATER_0_THERMISTOR 	= 1 << 1,
	HEATER_0_THERMOCOUPLE	= 1 << 2,

	HEATER_1_PRESENT		= 1 << 3,
	HEATER_1_THERMISTOR 	= 1 << 4,
	HEATER_1_THERMOCOUPLE 	= 1 << 5,

	DC_MOTOR_PRESENT		= 1 << 6,

	HBRIDGE_STEPPER			= 1 << 8,
	EXTERNAL_STEPPER		= 1 << 9,
	RELAY_BOARD				= 1 << 10,
	MK5_HEAD				= 1 << 11
};

/// Backoff stop time, in ms: 2 bytes
const static uint16_t BACKOFF_STOP_TIME         = 0x0004;
/// Backoff reverse time, in ms: 2 bytes
const static uint16_t BACKOFF_REVERSE_TIME      = 0x0006;
/// Backoff forward time, in ms: 2 bytes
const static uint16_t BACKOFF_FORWARD_TIME      = 0x0008;
/// Backoff trigger time, in ms: 2 bytes
const static uint16_t BACKOFF_TRIGGER_TIME      = 0x000A;


/// Extruder heater base location
const static uint16_t EXTRUDER_PID_BASE		= 0x000C;


/// HBP heater base location
const static uint16_t HBP_PID_BASE		= 0x0012;


/// Extra features word: 2 bytes
const static uint16_t EXTRA_FEATURES			= 0x0018;
enum {
	EF_SWAP_MOTOR_CONTROLLERS	= 1 << 0,
	EF_USE_BACKOFF				= 1 << 1,

	// Two bits to indicate mosfet channel.
	// Channel A = 0
	// Channel B = 1
	// Channel C = 2
	// Defaults:
	//   A - HBP heater
	//   B - extruder heater
	//   C - ABP motor
	EF_EX_HEATER_0			= 1 << 2,
	EF_EX_HEATER_1			= 1 << 3,
	EF_HBP_HEATER_0			= 1 << 4,
	EF_HBP_HEATER_1			= 1 << 5,
	EF_ABP_MOTOR_0			= 1 << 6,
	EF_ABP_MOTOR_1			= 1 << 7,

	// These are necessary to deal with horrible "all 0/all 1" problems
	// we introduced back in the day
	EF_ACTIVE_0				= 1 << 14,  // Set to 1 if EF word is valid
	EF_ACTIVE_1				= 1 << 15	// Set to 0 if EF word is valid
};

const static uint16_t EF_DEFAULT = 0x4084;

/// Extruder identifier; defaults to 0: 1 byte
const static uint16_t SLAVE_ID					= 0x001a;

const static uint16_t COOLING_FAN_BASE      = 0x001c;

const static uint16_t THERM_R0_OFFSET			= 0x00;
const static uint16_t THERM_T0_OFFSET			= 0x04;
const static uint16_t THERM_BETA_OFFSET			= 0x08;
const static uint16_t THERM_DATA_OFFSET			= 0x10;

/// Thermistor table 0
const static uint16_t THERM_TABLE_0             = 0x00f0;

/// Thermistor table 1
const static uint16_t THERM_TABLE_1   			= 0x0170;

void setDefaults();

} // namespace eeprom

#endif // EEPROM_MAP_HH_
