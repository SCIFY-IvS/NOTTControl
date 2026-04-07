MACIE Acquisition Software
==========================

*Authors:* Jarron Leisenring (University of Arizona)

*Description:* Acquisition software for MACIE controller

Software Operations
-------------------

Run command line executable:

    ./macieacq config_files/basic_slow_HxRG_warm.cfg

Commands:
1. testing true/false 
   - Enables offline software tests
0. powerOff
   - Shut down ASIC power
0. powerOn
   - Turn on ASIC power and reload firmware and default settings
   - Mainly for use after power off
0. initCamera
   - Select appropriate MACIE and ASIC registry Files.
   - Setup ASIC registry address map for local storage in ptUserData.
   - Check connection interfaces
   - Get handle for (currently USB connection only)
   - Get available MACIEs associated with handle
   - Initialize MACIE and ASIC
0. expSettings
   - Usage: expSettings --save bool -c ncoadds -i nseq -g ngroups -r nreads -s ndrops -k nresets
   - A reconfiguration sequence is included
0. frameSettings
   - Usage: frameSettings --xWin bool --yWin bool -x1 uint -x2 uint -y1 uint -y2 uint
0. set/getInputs
   - The four reference inputs, each spanning 4 bits.
   - Usage: setInputs 0xaaaa (for instance, aaaa = shorted inputs)
0. set/getGain
   - Preamp gain settings (16 possible settings).
   - Usage: setGain [0-15]
0. set/getCapComp
   - Preamp capacitive compensation settings (64 possible settings).
   - Recommended values in Table 3-10 of SIDECAR Manual.
   - Usage: setCapComp [0-63]
0. set/getFiltPole
   - Preamp low-pass filter settings (16 possible settings).
   - Set filter pole to 5-10 times the pixel clock rate.
   - Usage: setFiltPole [0-15]
0. set/getNOut
   - Number of outputs; only applicable to Slow Mode.
   - Usage: setNOut [1,2,4,16,32]
0. reconfigASIC
   - Necessary to reconfigure ASIC after updating values for registers h4???
0. acquire
   - Acquire frames from detector and download to PC.
0. haltAcq
   - Halt a failed acquisition
   - Runs CloseUSBScienceInterface() and HaltCameraAcq()
0. readASIC/writeASIC
   - Read/Write specific ASIC register
   - Address assumed to be in HEX, but val can be INT or HEX
   - Usage: writeASIC --addr 0x4000 --val 0x1
   - Usage: readASIC --addr 0x4000
0. readASIC_block
   - Read a number of contiguous registers 
   - Usage: readASIC_block --addr 0x6000 --nreg 16
0. readASICconfig
   - Parses detector and ASIC bias voltage and current settings
   - Usage: readASICconfig --addr 0x6000 --nreg 16
0. runTuneAcq
   - Run a tuning acquisition file
   - Files should be a sequence list of registers and values
      - Of form `reg_VBiasGate1 0x8550` or `0x6004 0x8550`
   - Data will be acquired and saved in current exposure and frame config
   - Usage: runTuneAcq filename.txt
0. readMACIE/writeMACIE
   - Read/Write specific MACIE register
   - Usage: readMACIE --addr 0x0010
   - Usage: writeMACIE --addr 0x0010 --val 0x27
0. printRegs
   - Print all stored ASIC registry information in RegMap
0. updateRegMap
   - Send registry update request to ASIC and store all values in ptUserData->RegMap
0. setParam/getParam
   - Update (or read) any ASIC setting defined in .cfg file
   - Usage: setParam --param (-p) Name --val (-v) 15 (or 0xf)
   - Usage: getParam --param (-p) Name
0. setClock/getClock
   - Set/print MACIE master clock rate.
   - Input value is in MHz (80 for Fast, 10 for Slow)
   - Usage: setClock [5-80]
0. setPhase/getPhase
   - Set/print MACIE clock phase shift setting.
   - Value always assumed to be in HEX.
   - Bit 8 is on/off. Bits 7-0 are phase value.
   - Usage: setPhase 0x01e0
0. findPhase
   - Cycle through a range of Phase Shift settings
   - Prints out number of error counts for each setting
   - Usage: findPhase --val1 0x01a0 --val2 0x01e0
0. setNBuffer/getNBuffer
   - Manually set/print the number of frame buffers in ptUserData->nBuffer.
   - In normal operations, this will be set optimally, depending on exposure settings.
   - sage: setNBuffer [1-100]
0. configBuffers
   - Configure nbuf, npixels, and Sci or Frame function
   - sciFunc should not be used along with buffsize and nbuf (??)
   - Usage: configBuffers --sciFunc bool --buffsize int --nbuf int
0. getErrors
   - Grab error counters from MACIE
0. resetErrors
   - Clear MACIE error counters
0. getPower
   - Print MACIE power structure on/off values
0. getVoltages
   - Print MACIE voltage settings
0. setLED
   - Set LED brightness (values 0-4)
   - Usage: setLED [0-4]
0. setVerbose/getVerbose
   - Set/print log levels to debug, info, warn, error

* TODO
   - Telemetry readback
   - readASICBits 0x0000<0:1>
   - ASIC Temperature sensors
   - Reset ASIC (run powerOff then powerOn?)
   - get/setOffset
   - Normal/enhanced mode in Slow Mode (?)
