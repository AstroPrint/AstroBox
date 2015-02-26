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

/** EEPROM storage offsets for cooling fan data */
namespace cooler_eeprom_offsets{
//$BEGIN_ENTRY
//$type:B 
const static uint16_t ENABLE_OFFSET   =     0;
//$BEGIN_ENTRY
//$type:B 
const static uint16_t SETPOINT_C_OFFSET  =  1;
}

/** EEPROM storage offsets for PID data */
namespace pid_eeprom_offsets{
//$BEGIN_ENTRY
//$type:H $floating_point:True
const static uint16_t P_TERM_OFFSET = 0;
//$BEGIN_ENTRY
//$type:H $floating_point:True
const static uint16_t I_TERM_OFFSET = 2;
//$BEGIN_ENTRY
//$type:H $floating_point:True
const static uint16_t D_TERM_OFFSET = 4;
}

/// mm offsets 
/// XDUAL: 135.862
/// XSINGLE: 119.362
/// Y: 75.218

/// steps per mm (from replicator.xml in RepG/machines)
/// XY : 94.139704
/// Z : 400

namespace replicator_axis_offsets{
	const static uint32_t DUAL_X_OFFSET = 12790;
	const static uint32_t SINGLE_X_OFFSET = 11237;
	const static uint32_t Y_OFFSET = 7081;
}

namespace toolhead_eeprom_offsets {
//// Uninitialized memory is 0xff.  0xff should never
//// be used as a valid value for initialized memory!

//// Feature map: 2 bytes
//$BEGIN_ENTRY
//$type:H 
const static uint16_t FEATURES			= 0x0000;
/// Backoff stop time, in ms: 2 bytes
//$BEGIN_ENTRY
//$type:H 
const static uint16_t BACKOFF_STOP_TIME         = 0x0002;
/// Backoff reverse time, in ms: 2 bytes
//$BEGIN_ENTRY
//$type:H 
const static uint16_t BACKOFF_REVERSE_TIME      = 0x0004;
/// Backoff forward time, in ms: 2 bytes
//$BEGIN_ENTRY
//$type:H 
const static uint16_t BACKOFF_FORWARD_TIME      = 0x0006;
/// Backoff trigger time, in ms: 2 bytes
//$BEGIN_ENTRY
//$type:H 
const static uint16_t BACKOFF_TRIGGER_TIME      = 0x0008;
/// Extruder heater base location: 6 bytes
//$BEGIN_ENTRY
//$eeprom_map:pid_eeprom_offsets
const static uint16_t EXTRUDER_PID_BASE         = 0x000A;
/// HBP heater base location: 6 bytes data
//$BEGIN_ENTRY
//$eeprom_map:pid_eeprom_offsets
const static uint16_t HBP_PID_BASE              = 0x0010;
/// Extra features word: 2 bytes
//$BEGIN_ENTRY
//$type:H 
const static uint16_t EXTRA_FEATURES            = 0x0016;
/// Extruder identifier; defaults to 0: 1 byte 
/// Padding: 1 byte of space
//$BEGIN_ENTRY
//$type:B 
const static uint16_t SLAVE_ID                  = 0x0018;
/// Cooling fan info: 2 bytes 
//$BEGIN_ENTRY
//$eeprom_map:cooler_eeprom_offsets
const static uint16_t COOLING_FAN_SETTINGS 	= 	0x001A;

// TOTAL MEMORY SIZE PER TOOLHEAD = 28 bytes
} 

namespace eeprom_offsets {
/// Firmware Version, low byte: 1 byte
//$BEGIN_ENTRY
//$type:B 
const static uint16_t VERSION_LOW				= 0x0000;
/// Firmware Version, high byte: 1 byte
//$BEGIN_ENTRY
//$type:B 
const static uint16_t VERSION_HIGH				= 0x0001;
/// Axis inversion flags: 1 byte.
/// Axis N (where X=0, Y=1, etc.) is inverted if the Nth bit is set.
/// Bit 7 is used for HoldZ OFF: 1 = off, 0 = on
//$BEGIN_ENTRY
//$type:B 
const static uint16_t AXIS_INVERSION			= 0x0002;
/// Endstop inversion flags: 1 byte.
/// The endstops for axis N (where X=0, Y=1, etc.) are considered
/// to be logically inverted if the Nth bit is set.
/// Bit 7 is set to indicate endstops are present; it is zero to indicate
/// that endstops are not present.
/// Ordinary endstops (H21LOB et. al.) are inverted.
//$BEGIN_ENTRY
//$type:B 
const static uint16_t ENDSTOP_INVERSION			= 0x0004;
/// Digital Potentiometer Settings : 5 Bytes
//$BEGIN_ENTRY
//$type:BBBBB 
const static uint16_t DIGI_POT_SETTINGS			= 0x0006;
/// axis home direction (1 byte)
//$BEGIN_ENTRY
//$type:B
const static uint16_t AXIS_HOME_DIRECTION 		= 0x000C;
/// Default locations for the axis in step counts: 5 x 32 bit = 20 bytes
//$BEGIN_ENTRY
//$type:iiiii 
const static uint16_t AXIS_HOME_POSITIONS_STEPS	= 0x000E;
/// Name of this machine: 16 bytes (16 bytes extra buffer) 
//$BEGIN_ENTRY
//$type:s  $length:16
const static uint16_t MACHINE_NAME				= 0x0022;
/// Tool count : 2 bytes
//$BEGIN_ENTRY
//$type:B 
const static uint16_t TOOL_COUNT 				= 0x0042;
/// Hardware ID. Must exactly match the USB VendorId/ProductId pair: 4 bytes
//$BEGIN_ENTRY
//$type:HH
const static uint16_t VID_PID_INFO				= 0x0044;
/// 40 bytes padding
/// Thermistor table 0: 128 bytes
//$BEGIN_ENTRY
//$eeprom_map:therm_eeprom_offsets
const static uint16_t THERM_TABLE				= 0x0074;
/// Padding: 8 bytes
// Toolhead 0 data: 28 bytes (see above)
//$BEGIN_ENTRY
//$eeprom_map:toolhead_eeprom_offsets $tool_index:0
const static uint16_t T0_DATA_BASE				= 0x0100;
// Toolhead 0 data: 28 bytes (see above)
//$BEGIN_ENTRY
//$eeprom_map:toolhead_eeprom_offsets $tool_index:1
const static uint16_t T1_DATA_BASE				= 0x011C;
/// axis lengths (mm) (6 bytes)
//$BEGIN_ENTRY
//$type:HHH
const static uint16_t AXIS_LENGTHS				= 0x0138;
/// 2 bytes padding
/// Light Effect table.
//$BEGIN_ENTRY
//$eeprom_map:blink_eeprom_offsets 
const static uint16_t LED_STRIP_SETTINGS		= 0x0140;
/// Buzz Effect table. 4 Bytes x 3 entries = 12 bytes
//$BEGIN_ENTRY
//$eeprom_map:buzz_eeprom_offsets
const static uint16_t BUZZ_SETTINGS		= 0x014A;
///  1 byte. 0x01 for 'never booted before' 0x00 for 'have been booted before)
//$BEGIN_ENTRY
//$type:B
const static uint16_t FIRST_BOOT_FLAG  = 0x0156;
/// 7 bytes, short int x 3 entries, 1 byte on/off
//$BEGIN_ENTRY
//$eeprom_map:preheat_eeprom_offsets
const static uint16_t PREHEAT_SETTINGS = 0x0158;
/// 1 byte,  0x01 for help menus on, 0x00 for off
//$BEGIN_ENTRY
//$type:B 
const static uint16_t FILAMENT_HELP_SETTINGS = 0x0160;
/// This indicates how far out of tolerance the toolhead0 toolhead1 distance is
/// in steps.  3 x 32 bits = 12 bytes
//$BEGIN_ENTRY
//$type:iii 
const static uint16_t TOOLHEAD_OFFSET_SETTINGS = 0x0162;


/// start of free space
const static uint16_t FREE_EEPROM_STARTS = 0x016D;


}

// buzz on/off settings
namespace buzz_eeprom_offsets{
//$BEGIN_ENTRY
//$type:HH 
const static uint16_t BASIC_BUZZ_OFFSET		= 0x00;
//$BEGIN_ENTRY
//$type:HH 
const static uint16_t ERROR_BUZZ_OFFSET 	= 0x04;
//$BEGIN_ENTRY
//$type:HH
const static uint16_t DONE_BUZZ_OFFSET		= 0x08;
}

//Offset table for the blink entries. 
namespace blink_eeprom_offsets{
//$BEGIN_ENTRY
//$type:B  
const static uint16_t BASIC_COLOR_OFFSET	= 0x00;
//$BEGIN_ENTRY
//$type:B  
const static uint16_t LED_HEAT_OFFSET	= 0x02;
//$BEGIN_ENTRY
//$type:BBB  
const static uint16_t CUSTOM_COLOR_OFFSET 	= 0x04;
}


/** thermal EERROM offset values and on/off settings for each heater */
namespace therm_eeprom_offsets{
//$BEGIN_ENTRY
//$type:i  
const static uint16_t THERM_R0_OFFSET                   = 0x00;
//$BEGIN_ENTRY
//$type:i  
const static uint16_t THERM_T0_OFFSET                   = 0x04;
//$BEGIN_ENTRY
//$type:i  
const static uint16_t THERM_BETA_OFFSET                 = 0x08;
//$BEGIN_ENTRY
//$type:H $mult:40
const static uint16_t THERM_DATA_OFFSET                 = 0x10;
}

/** preheat EERROM offset values and on/off settings for each heater */
namespace preheat_eeprom_offsets{
//$BEGIN_ENTRY
//$type:H  
const static uint16_t PREHEAT_RIGHT_OFFSET                = 0x00;
//$BEGIN_ENTRY
//$type:H  
const static uint16_t PREHEAT_LEFT_OFFSET                = 0x02;
//$BEGIN_ENTRY
//$type:H  
const static uint16_t PREHEAT_PLATFORM_OFFSET           = 0x04;
//$BEGIN_ENTRY
//$type:B  
const static uint16_t PREHEAT_ON_OFF_OFFSET             = 0x06;
}

// mask to set on/off settings for preheat
enum HeatMask{
    HEAT_MASK_PLATFORM = 0,
    HEAT_MASK_LEFT = 1,
    HEAT_MASK_RIGHT = 2
};


namespace eeprom_info {

//$BEGIN_ENTRY
//
const static uint16_t EEPROM_SIZE = 0x0200;
const int MAX_MACHINE_NAME_LEN = 16;


// EXTRA_FEATURES
enum {
	EF_SWAP_MOTOR_CONTROLLERS	= 1 << 0,
	EF_USE_BACKOFF			= 1 << 1,

	// Two bits to indicate mosfet channel.
	// Channel A = 0, B = 1, C = 2
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

// This is the set of flags for the Toolhead Features memory
enum {
        HEATER_0_PRESENT        = 1 << 0,
        HEATER_0_THERMISTOR     = 1 << 1,
        HEATER_0_THERMOCOUPLE   = 1 << 2,

        HEATER_1_PRESENT        = 1 << 3,
        HEATER_1_THERMISTOR     = 1 << 4,
        HEATER_1_THERMOCOUPLE   = 1 << 5,

        // Legacy settins for Cupcake and Thing-o-Matic
        DC_MOTOR_PRESENT                = 1 << 6,

        HBRIDGE_STEPPER                 = 1 << 8,
        EXTERNAL_STEPPER                = 1 << 9,
        RELAY_BOARD                     = 1 << 10,
        MK5_HEAD                        = 1 << 11
};


const static uint16_t EF_DEFAULT = 0x4084;



}

namespace eeprom {
	void factoryResetEEPROM();
	void fullResetEEPROM();
	void setToolHeadCount(uint8_t count);
    void setDefaultSettings();
    void setCustomColor(uint8_t red, uint8_t green, uint8_t blue);
    bool isSingleTool();
    void storeToolheadToleranceDefaults();
}
#endif // EEPROMMAP_HHe
