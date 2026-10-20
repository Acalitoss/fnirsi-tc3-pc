# DSO-TC3 V0.3 experimental USB protocol

USB identity: VID `19F5`, PID `5740`. Windows exposes a CDC serial port. The vendor updater selects 12,000,000 baud, 8N1. Our client disables DTR and RTS. These findings apply to the tested device and original V0.3 hash in the README.

## Stock firmware and bootloader

The stock normal-mode receive handler offers configuration read (`00`) and configuration write (`10`), not a waveform command. The request `00 01 00 00 01` produces an 18-byte configuration reply beginning `01 FE` in normal mode. The four following fields are big-endian unsigned 32-bit values; their physical meanings are not assigned by this project.

In bootloader mode the same request returns `01 01 00 00 02`. Upload frames are command byte, little-endian 16-bit counter, one-byte payload length, payload (up to 32 bytes), then the sum of all preceding bytes modulo 256. Acknowledgements use request command + 1, the same counter, zero payload length and checksum. Firmware write is `10`; restart is `20`.

The vendor uploader puts the complete file length into header bytes 6–9, little-endian, and sends the file in 32-byte chunks. Our encoder was compared byte-for-byte against all 11,437 vendor frames for the original image. The emulator simulation does not substitute for physical flash verification.

## Firmware layout

XOR each file byte with `7F` to expose the application. File offset `40` corresponds to flash address `08004000`. The replacement spans `08013F08` through `08014093`, including debugging strings used only by the original handler. Original vectors and all bytes outside this region remain unchanged.

The proprietary outer validation is not fully decoded. The original package header is preserved. Do not use the patch with a different hash or hardware revision.

## Experimental commands

| Request | Response |
|---|---|
| `00 00` | Original 18-byte configuration reply |
| `20 pp` | `A5 5A pp nn` then `nn` little-endian signed 16-bit sample words |
| `21 00` | `A5 5A 21 02` then vertical offset, scale index, timebase index, raw rate field, UI focus; 24 bytes total |
| `22 pp` | `A5 5A pp 38` then 56 bytes of Sys state; pages 0–3; 60 bytes total |
| `30 kk` | `A5 5A 30 ss`; status 0 accepted, 1 busy |

Sample pages 0–19 contain 29 words each, page 20 contains 20: 600 total. The stock transmit helper rejects lengths ≥64, so responses stay below 64 bytes. Unsupported commands and out-of-range pages are ignored. Device state and measurements are read-only through `22`.

`30` is accepted only in oscilloscope mode 3. Keys `02`, `04`, `08`, `10`, `20` use the existing short-key mailbox. Key `84` represents long-left, used by the original firmware for RUN/HOLD; its previous long-key latch is released before injection. The client waits for the mailbox to empty, then reads back the setting. No arbitrary memory-write command is exposed.

## Sys state

Sys base is `20000668`. Offsets:

| Offset | Field |
|---|---|
| 20 | device mode |
| 24 | signed vertical display offset |
| 28 / 2C / 30 | scale / probe / timebase indices |
| 34 / 3C / 40 | coupling / trigger mode / trigger edge |
| 90 / 91 | key status / key code |
| A1 | device HOLD flag |
| A8 | trigger sample offset |
| B4 / B8 / BC | float Vmax / Vmin / Vpp, volts |
| C0 / C4 | float Vrms / Vavg, volts |
| C8 / CC / D0 | float frequency (kHz) / duty (%) / cycle (ms) |

UI focus is at `20000144`. Measurement offsets were traced to the stock screen formatting routine at `08011B38`. Sample words at Sys+`594` are **signed display displacements after ADC conversion**, not raw ADC codes. The stock drawing path renders a trigger-selected 300-point window.

State pages and sample pages are not an atomic snapshot. Host and device setting values may briefly differ while the acquisition loop updates; independent accuracy and AC timing validation remain open work.


## Development protocol 3

Metadata signature is `A5 5A 21 03`. State pages 0–31 each return 56 bytes, covering a fixed 1792-byte range starting at `0x20000668`. No arbitrary address reads or writes are provided. Remote short keys 1/2/4/8/16/32 mean Back/OK/Left/Up/Right/Down; long-left is 0x84. Accepted only in modes 1–6. Power and long-OK are excluded. The original firmware dispatcher processes the key mailbox; the PC never calls hardware functions directly.

Mode values: 1 Home, 2 M-Tester, 3 Oscilloscope, 4 Generator, 5 Tools, 6 Settings. Home index at +0x1c: Tester/Scope/Generator/Tools. Instrument selection at +0x94: Generator Sine/Square/Pulse/Triangle/Ramp/DC; Tools ON-OFF/Voltage/DS18B20/DHT11/IR Decode/Calibrate.

Generator fields: +0x48 uint frequency Hz; +0x4c uint duty percent; +0x50 float amplitude V. Tools +0xd8 float voltage; +0x13c temperature; +0x140 humidity; +0x150 IR received byte; +0x154 IR code. Sensor values are shown only for corresponding result types 18/19. M-Tester union +0xe0 type, +0xe8/+0xec/+0xf0 zero-based pin indices. Result float fields are type-dependent, not interchangeable with oscilloscope fields. See instrument.py; several device result types still need full decoding and physical validation.

Real-device check: four mode changes and return to home, all six generator wave selections, 5000→6000→5000 Hz readback, Tools indices 0–4, and OK-triggered component test. Test socket was not populated with a reference component during this check. Calibration was not executed. Only oscilloscope mode reads waveform pages; other modes return no waveform, avoiding stale traces.
