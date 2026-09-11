# Hardware: the constrained real design

Researched 2026-09-11. Every number below has a source; the ones we could not
source are marked *unverified* and must be measured on the bench first.

## Recommendation in one paragraph

A **Creality Ender 3-class Cartesian gantry** (Marlin firmware, G-code over
USB) is the positioner. Each LED or resistor is pre-mounted on a 3D-printed
**cartridge** with 0.64 mm square header pins, so the robot only ever handles
one rigid, identical object. A **vacuum pickup nozzle** with a hard mechanical
shoulder rides on the printer's leadscrew Z axis and presses the cartridge
into the board. A **Raspberry Pi 5** is both the device under test (GPIO to
the breadboard through gpiozero) and the host for the camera and the printer's
serial link. A **Pi Camera Module 3** is fixed 30 cm above the bed, and four
**ArUco markers** on the board corners give the pixel-to-hole mapping. Rough
total is about $350. Nothing with an articulated arm under $300 comes near the
0.5 mm repeatability the task needs; the gantry has it out of the box.

## 1. Breadboard facts the sim must respect

| fact | value | source |
|---|---|---|
| pitch | 2.54 mm both axes | [BusBoard BB400](https://www.digikey.com/en/products/detail/busboard-prototype-systems/BB400/19200389) |
| 830-point board | 165.1 x 54.6 x 8.5 mm; 63 rows x 5 x 2 strips + 4 rails x 50 | [Elegoo datasheet](http://www.pgccphy.net/1020/datasheets/ELEGOO%20830%20430%20tie-points%20Breadboard.pdf) |
| accepted lead | 0.41-0.71 mm (3M spec), 20-29 AWG | [3M brochure](https://www.mouser.com/catalog/specsheets/Brochure_Solderless_Breadboard-6989311.pdf) |
| hole opening | ~1.0-1.1 mm, chamfered | [electro-tech-online](https://www.electro-tech-online.com/threads/diameter-of-breadboard-holes-incompatible-with-size-of-components-pins-and-jumper-wires-etc.163161/) |
| 0.64 mm square header pin | the canonical breadboard pin | same thread |
| lateral capture per pin | about +-0.25 mm before the tip hits plastic; a chamfered tip roughly doubles it | derived from the above |
| contact life | 50,000 insertions on name-brand boards | [ProtoSupplies](https://protosupplies.com/guide-to-solderless-breadboards/) |
| insertion force | *unverified*: 1-3 N per pin, 2-6 N for a 2-pin part. Measure with a kitchen scale on day one | no vendor publishes it |

Sim parameter: `placement_tolerance_mm` starts at 0.5 in v0.1 and drops to
0.25 (with a 0.5 "chamfer" that turns a near miss into `misaligned` rather
than `inserted`) at v0.5.

## 2. Positioner: why a gantry and not an arm

| candidate | cost | repeatability | interface | verdict |
|---|---|---|---|---|
| Ender 3 / V3 SE | $159-279 new, ~$100 used ([Creality](https://www.creality.com/products/creality-ender-3-v3-se)) | spec +-0.1 mm ([Creality](https://www.crealityofficial.co.uk/products/official-creality-ender-3-3d-printer)); an Ender 3 V2 converted to pick-and-place held 0.1 mm ([3DPlacer](https://www.xpdiy.io/2023/07/29/convert-ender3-v2-to-pick-and-place-machine/)) | Marlin G-code over USB; `M400` waits for motion, `M114` reports position ([Marlin](https://marlinfw.org/docs/gcode/M114.html)) | **pick** |
| AxiDraw / NextDraw plotter | $699 ([Bantam](https://bantamtools.com/products/bantam-tools-nextdraw-8511)) | <0.1 mm XY | Python API | Z is a pen lift with no press force |
| Cheap GRBL plotter kit | $80-120 | unspecified | GRBL | assembly eats the weekend, no press force |
| LeRobot SO-100/101 | $100-500 ([TechCrunch](https://techcrunch.com/2025/04/28/hugging-face-releases-a-3d-printed-robotic-arm-starting-at-100)) | +-2-4 mm at the tip ([Robotics Center](https://www.roboticscenter.ai/learn/robot-arms/openarm-vs-so101)); STS3215 backlash ~1.3 deg = 6.8 mm at 300 mm ([Robo9](https://robonine.com/testing-of-feetech-sts3215-servomotor-backlash-repeatability-and-torque/)) | Python | 4-8x the capture radius |
| myCobot 280 | $499-599 | +-0.5 mm claimed ([Elephant](https://www.elephantrobotics.com/en/mycobot-280-m5-new-specificatons-en/)) | pymycobot | over budget, marginal |
| Rotrics DexArm | $1,049 | 0.05 mm claimed | G-code | 3x budget |
| small SCARA kits | <$200-$3k | 3.5 mm or unpublished | custom | no |

The board is a planar 2.54 mm grid; the job is "go to (x, y), press straight
down 8 mm". A gantry's error is roughly constant across the bed and its Z is a
leadscrew that pushes with kilograms. An arm's tip error is angle times reach,
it needs inverse kinematics and 6-DoF hand-eye calibration, and its wrist must
hold the pins vertical during the press. That is why `ArmAPI` is XY plus a
binary lift: it is the gantry's real interface, not a simplification of an arm.

## 3. End effector

- **Vacuum nozzle (pick):** aquarium pump run in reverse or a 12 V mini vacuum
  pump, a 12 V solenoid valve, and a blunt 0.9 mm needle, the standard hobby
  pick-and-place head ([Hackaday DIY PnP](https://hackaday.io/project/9319-diy-pick-and-place),
  [OpenPnP vacuum](https://github.com/openpnp/openpnp/wiki/Setup-and-Calibration_Vacuum-Setup)).
  Vacuum holds the cartridge; a shoulder on the nozzle body transmits the press
  force from the Z axis so the seal never carries it.
- **Servo gripper:** works, but adds an actuator and a grip-angle error.
- **Electromagnet + steel tab:** one MOSFET on a GPIO pin, but residual
  magnetism on release makes it second choice.
- **Force:** budget 2-6 N. A pen-lift servo linkage is sized for a pen's
  weight, which is why plotters are out; the Ender's leadscrew Z is not
  force-limited in this range.

In the sim, `open_gripper` maps to "vacuum off" and `close_gripper` to
"vacuum on"; the names stay generic so the backend can be a servo gripper.

## 4. Cartridges (the highest-leverage decision)

A 10 x 10 x 8 mm printed block with a male header epoxied in: 2 adjacent pins
for a 5 mm LED (lead pitch is natively 2.54 mm, 0.5 mm square leads,
[Components101](https://components101.com/diodes/5mm-round-led)), and a
4-position header with the outer pins used (10.16 mm apart) for a resistor,
which matches the standard 0.4" axial lead forming
([IEC 60062 / EIA RS-253 summary](https://industrialmonitordirect.com/blogs/knowledgebase/axial-resistor-size-to-wattage-guide-dimension-standards-and-identification)).
Leads are trimmed and soldered to the header top. Polarity is the block's
orientation, marked with an arrow the camera can read. Chamfer the pin tips.

This converts a deformable-lead problem into peg-in-hole with 0.25 mm slack.
It is why `hwctl/world` models cartridges with pin offsets and never leads.

Prior art is thin: OpenPnP/LumenPnP are SMT only with no through-hole
insertion mode ([OpenPnP FAQ](https://github.com/openpnp/openpnp/wiki/Build-FAQ));
[3DPlacer](https://github.com/xpDIY/3DPlacer) (Ender 3 V2 to OpenPnP) is the
closest hardware analogue; US patent 11,079,742 automates breadboard *wiring*
with switch matrices, not insertion. No automated breadboarding project was
found, which is a good sign for the hackathon story.

## 5. Vision

- **Pi Camera Module 3**, 12 MP, autofocus, ~$25 ([Raspberry Pi](https://www.raspberrypi.com/news/new-autofocus-camera-modules/)).
  Use `picamera2` (libcamera); the legacy `picamera` stack is gone.
- **Resolution:** 165 mm across 1920 px is 11.6 px/mm, about 29 px per pitch
  and 12 px per hole. 1080p is enough; full 4608 px stills only for calibration.
- **Fiducials:** four ArUco markers at the board corners, `findHomography`
  with `CORNER_REFINE_SUBPIX` ([OpenCV ArUco](https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html)).
  This is why the sim renderer draws the same markers from v0.5.
- **Lit-LED detection:** lock exposure and gain, difference a dark and a lit
  frame inside each LED's region, threshold on HSV value (30-50 % delta).
  Auto-exposure is failure mode #5 below.
- A USB webcam (Logitech C270/C920) works through V4L2 if the host is a laptop.

## 6. The Raspberry Pi as device under test

- **Model:** Pi 5 4 GB (~$65) or Pi 4 1 GB (~$35) ([2026 pricing guide](https://magazinmehatronika.com/en/the-2026-raspberry-pi-pricing-and-buying-guide/)). A Zero 2 W is too weak to also run OpenCV and the serial link.
- **GPIO library:** RPi.GPIO does not work on the Pi 5 (RP1 I/O chip). Use
  gpiozero (pre-installed) with the lgpio backend
  ([Raspberry Pi white paper](https://pip-assets.raspberrypi.com/categories/685-whitepapers-app-notes/documents/RP-006553-WP/A-history-of-GPIO-usage-on-Raspberry-Pi-devices-and-current-best-practices)).
  `gpiozero.LED(17).on()` is the whole API. The orchestrator's generated Pi
  scripts must be told this.
- **Electrical:** 3.3 V logic, pad drive 2-16 mA, keep total GPIO current
  under ~50 mA ([RPi GPIO docs](https://github.com/raspberrypi/documentation/blob/master/documentation/asciidoc/computers/raspberry-pi/gpio-on-raspberry-pi.adoc)).
  V_OH under load is ~2.6 V minimum, so a red LED with 330 ohm draws 2.4-4.5 mA
  and 1 kohm (~1.5 mA) still lights it. The sim's 40 ohm series model
  reproduces the 3.1 V loaded output ngspice gives.
- **Hosting:** the one Pi runs the CSI camera, the USB serial to the printer,
  and the GPIO harness. The printer has its own PSU.

## 7. Circuit simulation

ngspice is at version 47 (Aug 2026, [news](https://ngspice.sourceforge.io/news.html));
version 42 from Debian/Ubuntu apt is what the dev container has and it runs
our decks. PySpice's last release is 1.5.0 from 2021 with support up to
ngspice 34 ([GitHub](https://github.com/PySpice-org/PySpice)); treat it as
unmaintained and use `ngspice -b deck.cir` through `subprocess`. The verified
deck and LED model are in `docs/01-architecture.md`; a fuller red LED model
(`IS=93.2p RS=42m N=3.73`) from the
[All About Circuits forum](https://forum.allaboutcircuits.com/threads/led-spice-model-in-eagle.191587/)
can replace it when brightness matters.

## 8. Ready-made alternatives

None trivialise the project. LumenPnP is $1,995 and SMT only
([Opulo](https://www.opulo.io/products/lumenpnp)); arm kits with vision
(Hiwonder SO-ARM101, myCobot camera kits) inherit the arm repeatability problem.

## 9. Bill of materials (2026 USD)

| item | price |
|---|---|
| Creality Ender 3 V3 SE (or used Ender 3, ~$100) | $180 |
| Raspberry Pi 5 4 GB + PSU + SD | $85 |
| Pi Camera Module 3 + 30 cm cable | $30 |
| 830-point breadboard, name brand (BusBoard / 3M) | $8 |
| 12 V mini vacuum pump, solenoid valve, tubing, MOSFET board | $25 |
| blunt needles, Luer adapter | $6 |
| header strips, 5 mm LEDs, resistors, epoxy | $10 |
| PLA for cartridges, nozzle mount, camera arm, marker frame | $5 |
| **total** | **about $350** |

## What will fail first (ranked) and what the sim does about it

1. **Insertion alignment and force.** Pins skate on the chamfer or the seal
   gives before the pin seats. Bench: hard shoulder, chamfered pins, a +-0.2 mm
   X wiggle on the way down. Sim: `misaligned` outcome and tolerance model (v0.4-v0.5).
2. **Camera-to-machine calibration drift.** Homography maps camera to board,
   but board to printer needs a 3-point touch-off at the markers. Sim: the
   fiducial pipeline runs on rendered frames first (v0.5), the `gcode` backend
   owns a work-offset calibration routine (v0.7).
3. **Breadboard spring variability.** Loose holes drop parts, tight ones stall
   the press. Buy name-brand. Sim: random drop injection (v0.4).
4. **Marlin serial flow control.** Sending G-code without waiting for `ok` and
   `M400` desynchronises motion from vision. Sim: timed motion and a `busy`
   state so the orchestrator learns to wait (v0.5).
5. **Auto-exposure ruining LED detection.** Lock exposure in picamera2.
6. **Wrong GPIO library on Pi 5.** Pin gpiozero in the orchestrator prompt.
7. **Cartridge print tolerances.** FDM shrink makes header holes tight; print a
   test strip first.
8. **Z clearance.** Retract 10 mm before XY moves so a held cartridge does not
   clip neighbours. Sim: `move_to` refuses to move while lowered.

## Day-one hardware tests (before buying anything else)

1. Push a bare 2-pin header into the board by hand on a kitchen scale: record
   the force. Replace the *unverified* number above.
2. Tape a header pin to the Ender's hotend carriage, jog it over an empty board
   with `G0`, lower with `G0 Z`, and see whether it seats. That is the entire
   risk budget in a 30-minute test.
