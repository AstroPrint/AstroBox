/*
 * Copyright 2010 by Adam Mayer <adam@makerbot.com>
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


#ifndef EEPROMMAP_HH_
#define EEPROMMAP_HH_

#include <stdint.h>

enum {
	ESTOP_CONF_NONE = 0x0,
	ESTOP_CONF_ACTIVE_HIGH = 0x1,
	ESTOP_CONF_ACTIVE_LOW = 0x2
};

namespace eeprom_offsets {

const static uint16_t EEPROM_SIZE				= 0x0200;

/// Version, low byte: 1 byte
//$BEGIN_ENTRY
//$type:B $ignore:True
const static uint16_t VERSION_LOW				= 0x0000;

/// Version, high byte: 1 byte
//$BEGIN_ENTRY
//$type:B $ignore:True
const static uint16_t VERSION_HIGH				= 0x0001;

/// Axis inversion flags: 1 byte.
/// Axis N (where X=0, Y=1, etc.) is inverted if the Nth bit is set.
/// Bit 7 is used for HoldZ OFF: 1 = off, 0 = on
//$BEGIN_ENTRY
//$type:B $axis_expand:True 
const static uint16_t AXIS_INVERSION			= 0x0002;

/// Endstop inversion flags: 1 byte.
/// The endstops for axis N (where X=0, Y=1, etc.) are considered
/// to be logically inverted if the Nth bit is set.
/// Bit 7 is set to indicate endstops are present; it is zero to indicate
/// that endstops are not present.
/// Ordinary endstops (H21LOB et. al.) are inverted.
//$BEGIN_ENTRY
//$type:B $axis_expand:True 
const static uint16_t ENDSTOP_INVERSION			= 0x0003;

/// Name of this machine: 16 bytes
//$BEGIN_ENTRY
//$type:s $length:16
const static uint16_t MACHINE_NAME				= 0x0020;

/// Default locations for the axis: 5 x 32 bit = 20 bytes
//$BEGIN_ENTRY
//$type:IIIII
const static uint16_t AXIS_HOME_POSITIONS		= 0x0060;

// Estop configuration byte: 1 byte.
//$BEGIN_ENTRY
//$type:B $tooltip: 0 None, 1 Active High, 2 Active Low
const static uint16_t ESTOP_CONFIGURATION = 0x0074;

//$BEGIN_ENTRY
//$type:B
const static uint16_t TOOL0_TEMP      		= 0x0080;

//$BEGIN_ENTRY
//$type:B
const static uint16_t TOOL1_TEMP      		= 0x0081;

//$BEGIN_ENTRY
//$type:B
const static uint16_t PLATFORM_TEMP   		= 0x0082;

//$BEGIN_ENTRY
//$type:B $ignore:True
const static uint16_t EXTRUDE_DURATION		= 0x0083;

//$BEGIN_ENTRY
//$type:B $ignore:True
const static uint16_t EXTRUDE_MMS     		= 0x0084;

//$BEGIN_ENTRY
//$type:B $ignore:True
const static uint16_t MOOD_LIGHT_SCRIPT		= 0x0085;

//$BEGIN_ENTRY
//$type:B
const static uint16_t MOOD_LIGHT_CUSTOM_RED	= 0x0086;

//$BEGIN_ENTRY
//$type:B
const static uint16_t MOOD_LIGHT_CUSTOM_GREEN	= 0x0087;

//$BEGIN_ENTRY
//$type:B
const static uint16_t MOOD_LIGHT_CUSTOM_BLUE	= 0x0088;

//Bit 1 is Model mode or user view mode (user view mode = bit set)
//Bit 2-4 are the jog mode distance 0 = short, 1 = long, 2 = cont
//$BEGIN_ENTRY
//$type:B $ignore:True
const static uint16_t JOG_MODE_SETTINGS		= 0x0089;

//0 = No system buzzing, >=1 = number of repeats to buzz for
//$BEGIN_ENTRY
//$type:B
const static uint16_t BUZZER_REPEATS		= 0x008A;

//Steps per mm, each one is 8 bytes long and are stored as int64_t
//$BEGIN_ENTRY
//$type:q  $unit:steps * 10000000000
const static uint16_t STEPS_PER_MM_X		= 0x008B;

//Steps per mm, each one is 8 bytes long and are stored as int64_t
//$BEGIN_ENTRY
//$type:q  $unit:steps * 10000000000
const static uint16_t STEPS_PER_MM_Y		= 0x0093;

//Steps per mm, each one is 8 bytes long and are stored as int64_t
//$BEGIN_ENTRY
//$type:q  $unit:steps * 10000000000
const static uint16_t STEPS_PER_MM_Z		= 0x009B;

//Steps per mm, each one is 8 bytes long and are stored as int64_t
//$BEGIN_ENTRY
//$type:q  $unit:steps * 10000000000
const static uint16_t STEPS_PER_MM_A		= 0x00A3;

//Steps per mm, each one is 8 bytes long and are stored as int64_t
//$BEGIN_ENTRY
//$type:q  $unit:steps * 10000000000
const static uint16_t STEPS_PER_MM_B		= 0x00AB;

//int64_t (8 bytes) The filament used in steps
//$BEGIN_ENTRY
//$type:q
const static uint16_t FILAMENT_LIFETIME_A	= 0x00B3;
//$BEGIN_ENTRY
//$type:q
const static uint16_t FILAMENT_TRIP_A		= 0x00BB;

//Number of ABP copies (1-254) when building from SDCard (1 byte)
//$BEGIN_ENTRY
//$type:B
const static uint16_t ABP_COPIES		= 0x00C3;

//$BEGIN_ENTRY
//$type:B $ignore:True
const static uint16_t UNUSED1			= 0x00C4;

//Override the temperature set in the gcode file at the start of the build
//0 = Disable, 1 = Enabled
//$BEGIN_ENTRY
//$type:B $constraints:l,0,1
const static uint16_t OVERRIDE_GCODE_TEMP	= 0x00C5;

//Profiles
#define PROFILE_NAME_LENGTH			8
#define PROFILE_HOME_OFFSETS_SIZE		(4 * 3)		//X, Y, Z (uint32_t)

#define PROFILE_NEXT_OFFSET			(PROFILE_NAME_LENGTH + \
						 PROFILE_HOME_OFFSETS_SIZE + \
						 4 )		//24 (0x18)    4=Bytes (Hbp, tool0, tool1, extruder)

//4 Profiles = 0x00C6 + PROFILE_NEXT_OFFSET * 4 
const static uint16_t PROFILE_BASE		= 0x00C6;

//1 = Acceleration On, 0 = Acceleration Off
//$BEGIN_ENTRY
//$type:B $constraints:l,0,1 $tooltip:Set to 1 to use acceleration.  0 for no acceleration.  Note that you must turn acceleration on to print safely at speeds over 50mm/s.
const static uint16_t ACCELERATION_ON		= 0x0126;

//uint32_t (4 bytes)
//$BEGIN_ENTRY
//$type:I $unit:mm/min
const static uint16_t ACCEL_MAX_FEEDRATE_X	= 0x0127;
//$BEGIN_ENTRY
//$type:I $unit:mm/min
const static uint16_t ACCEL_MAX_FEEDRATE_Y	= 0x012B;
//$BEGIN_ENTRY
//$type:I $unit:mm/min
const static uint16_t ACCEL_MAX_FEEDRATE_Z	= 0x012F;
//$BEGIN_ENTRY
//$type:I $unit:mm/min
const static uint16_t ACCEL_MAX_FEEDRATE_A	= 0x0133;
//$BEGIN_ENTRY
//$type:I $unit:mm/min
const static uint16_t ACCEL_MAX_FEEDRATE_B	= 0x0137;

//uint32_t (4 bytes)
//$BEGIN_ENTRY
//$type:I $unit:mm/s/s
const static uint16_t ACCEL_MAX_ACCELERATION_X	= 0x013B;
//$BEGIN_ENTRY
//$type:I $unit:mm/s/s
const static uint16_t ACCEL_MAX_ACCELERATION_Y	= 0x013F;
//$BEGIN_ENTRY
//$type:I $unit:mm/s/s
const static uint16_t ACCEL_MAX_ACCELERATION_Z	= 0x0143;
//$BEGIN_ENTRY
//$type:I $unit:mm/s/s
const static uint16_t ACCEL_MAX_ACCELERATION_A	= 0x0147;

//uint32_t (4 bytes)
//$BEGIN_ENTRY
//$type:I
const static uint16_t ACCEL_MAX_EXTRUDER_NORM	= 0x014B;
//$BEGIN_ENTRY
//$type:I
const static uint16_t ACCEL_MAX_EXTRUDER_RETRACT= 0x014F;

//uint32_t (4 bytes)
//$BEGIN_ENTRY
//$type:I  $unit:mm/s * 10 $ignore:True
const static uint16_t UNUSED2	= 0x0153;

//$BEGIN_ENTRY
//$type:I  $unit:mm/s * 10 $ignore:True
const static uint16_t UNUSED3			= 0x0157;
//$BEGIN_ENTRY
//$type:I  $unit:mm/s * 10 $ignore:True
const static uint16_t UNUSED4			= 0x015B;
//$BEGIN_ENTRY
//$type:I  $unit:factor * 100000
const static uint16_t ACCEL_ADVANCE_K2		= 0x015F;
//$BEGIN_ENTRY
//$type:I $ignore:True
const static uint16_t UNUSED5			= 0x0163;
//$BEGIN_ENTRY
//$type:I  $unit:factor * 100000
const static uint16_t ACCEL_ADVANCE_K		= 0x0167;
//$BEGIN_ENTRY
//$type:I  $unit:mm/s * 100 $ignore:True
const static uint16_t UNUSED6			= 0x016B;
//$BEGIN_ENTRY
//$type:I  $unit:mm/s * 10000 $ignore:True
const static uint16_t UNUSED7			= 0x016F;

//uint8_t (1 byte)
//$BEGIN_ENTRY
//$type:B $tooltip: character dimensions of your LCD, 0 16x4, 50 20x4, 51 24x4   
const static uint16_t LCD_TYPE			= 0x0173;

//uint8_t (1 byte)
//Bitwise (true = endstop present)
//1 = X Min
//2 = X Max
//4 = Y Min
//8 = Y Max
//16 = Z Min
//32 = Z Max
//$BEGIN_ENTRY
//$type:B $tooltip:A bitfield representing presence/absence (0/1) of endstops [0,0,ZMax,ZMin,YMax,YMin,XMax,XMin]
const static uint16_t ENDSTOPS_USED		= 0x0174;

//uint32_t (4 bytes) Homing feed rate in mm/min
//$BEGIN_ENTRY
//$type:I $unit:mm/min
const static uint16_t HOMING_FEED_RATE_X	= 0x0175;
//$BEGIN_ENTRY
//$type:I $unit:mm/min
const static uint16_t HOMING_FEED_RATE_Y	= 0x0179;
//$BEGIN_ENTRY
//$type:I $unit:mm/min
const static uint16_t HOMING_FEED_RATE_Z	= 0x017D;

//$BEGIN_ENTRY
//$type:I $ignore:True
const static uint16_t UNUSED8			= 0x0181;
//$BEGIN_ENTRY
//$type:i  $unit:steps $constraints:m,-32767,32767
const static uint16_t ACCEL_EXTRUDER_DEPRIME_A	= 0x0185;
//$BEGIN_ENTRY
//$type:B $constraints:l,0,1
const static uint16_t ACCEL_SLOWDOWN_FLAG	= 0x0189;
//$BEGIN_ENTRY
//$type:BBB $ignore:True
const static uint16_t UNUSED9			= 0x018A;
//$BEGIN_ENTRY
//$type:I $ignore:True
const static uint16_t UNUSED10			= 0x018D;

//uint8_t (1 byte)
//$BEGIN_ENTRY
//$type:B $ignore:True
const static uint16_t UNUSED11			= 0x0191;

//uint32_t (4 bytes)
//$BEGIN_ENTRY
//$type:I $unit:mm/s * 10
const static uint16_t ACCEL_MAX_SPEED_CHANGE_X= 0x0192;
//$BEGIN_ENTRY
//$type:I  $unit:mm/s * 10
const static uint16_t ACCEL_MAX_SPEED_CHANGE_Y= 0x0196;
//$BEGIN_ENTRY
//$type:I  $unit:mm/s * 10
const static uint16_t ACCEL_MAX_SPEED_CHANGE_Z= 0x019A;
//$BEGIN_ENTRY
//$type:I $unit:mm/s * 10 
const static uint16_t ACCEL_MAX_SPEED_CHANGE_A= 0x019E;
//$BEGIN_ENTRY
//$type:I  $unit:mm/s * 10
const static uint16_t ACCEL_MAX_SPEED_CHANGE_B= 0x01A2;
//$BEGIN_ENTRY
//$type:I $unit:mm/s/s
const static uint16_t ACCEL_MAX_ACCELERATION_B= 0x01A6;
//$BEGIN_ENTRY
//$type:i  $unit:steps $constraints:m,-32767,32767
const static uint16_t ACCEL_EXTRUDER_DEPRIME_B= 0x01AA;
// Tool count : 1 bytes
//$BEGIN_ENTRY
//$type:B
const static uint16_t TOOL_COUNT	      = 0x01AE;
// This indicates how far out of tolerance the toolhead0 toolhead1 distance is
// in steps.  3 x int32_t bits = 12 bytes
//$BEGIN_ENTRY
//$type:iii $unit:steps
const static uint16_t TOOLHEAD_OFFSET_SETTINGS = 0x01B0;
// axis lengths XYZAB 5*uint32_t = 20 bytes
//$BEGIN_ENTRY
//$type:iiiii $unit:steps $constraints:m,0,2147483647
const static uint16_t AXIS_LENGTHS	       = 0x01BC;

#ifdef STORE_RAM_USAGE_TO_EEPROM
//4 bytes
//$BEGIN_ENTRY
//$type:I $ignore:True
const static uint16_t RAM_USAGE_DEBUG = 0x01D0;
#endif

//int64_t (8 bytes) The filament used in steps
//$BEGIN_ENTRY
//$type:q
const static uint16_t FILAMENT_LIFETIME_B	= 0x01D4;

//$BEGIN_ENTRY
//$type:B $constraints:l,0,1
const static uint16_t DITTO_PRINT_ENABLED	= 0x01DC;

//int64_t (8 bytes) The filament trip counter
//$BEGIN_ENTRY
//$type:q
const static uint16_t FILAMENT_TRIP_B		= 0x01DD;

//Hardware vendor id (in this case, Sailfish vendor id) - (4 bytes)
//$BEGIN_ENTRY
//$type:BBBB $ignore:True
const static uint16_t VID_PID_INFO		 = 0x1E5;

//Extruder hold (1 byte)
//$BEGIN_ENTRY
//$type:B $constraints:l,0,1
const static uint16_t EXTRUDER_HOLD		 = 0x1E9;

//Toolhead offset system (1 byte)
//$BEGIN_ENTRY
//$type:B $constraints:l,0,1 $tooltip:checked indicates new system
const static uint16_t TOOLHEAD_OFFSET_SYSTEM     = 0x1EA;

//Use SD card CRC checks (1 byte)
//$BEGIN_ENTRY
//$type:B  $tooltip:1=enabled, all other values=disabled
const static uint16_t SD_USE_CRC             = 0x1EB;

/// Reset Jetty Firmware defaults only
void setJettyFirmwareDefaults();

/// Reset all data in the EEPROM to a default.
void setDefaults(bool retainCounters);

void storeToolheadToleranceDefaults();

void verifyAndFixVidPid();

} // namespace eeprom

#endif // EEPROMMAP_HH_
