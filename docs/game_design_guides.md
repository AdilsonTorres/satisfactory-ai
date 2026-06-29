# Satisfactory Game Design & Factory Layout Guides

This document compiles core factory design principles, logistics patterns, and structure layout guidelines collected from community wikis and web search guides. These patterns can be directly used by the automation bot to plan layouts, align structures, and navigate factory floors.

---

## 📐 1. Blueprint Design Best Practices

Creating modular, snap-aligned blueprints is the key to scaling factory floors without compounding alignment mistakes.

### 🧱 Modular Block Architecture
Instead of building custom "all-in-one" factories for every new tier, build reusable production blocks.
* **Single-Purpose Modules:** Design blueprints for specific tasks (e.g., a "Smelter Block" containing 8 Smelters, or an "Assembler Block" with 4 Assemblers).
* **Straight-Through Logistics:** Keep inputs on one side and outputs on the opposite side. When aligned, these modules snap together end-to-end to multiply production without custom belt routing.
* **Merger/Splitter Integration:** Pre-install Splitters on input belts and Mergers on output belts at the blueprint's borders. This enables daisy-chaining adjacent modules with zero extra space.

> [!TIP]
> **Breathing Room Rule:** Always leave a 1-meter (half-foundation) walkway between rows of machines. This prevents clipping, simplifies manual debugging, and leaves space for power poles.

---

## 🔌 2. Factory Floor Topologies

Effective spatial separation is critical for keeping factory layouts clean and high-throughput.

### 🔀 Sandwich Logistics Floors
To keep the main factory floor walkable and neat, separate the machinery from the conveyor belts and pipes.
* **Logistics Sub-floors:** Build a 1-to-2 meter sub-floor directly beneath the machines.
* **Conveyor Lifts:** Route raw materials via conveyor lifts straight up through the floor foundations into machine inputs.
* **Clean Floors:** Keeps the main floor 100% clean and free of belt spaghetti, reducing bot collision issues.

### 🏢 Vertical Stacking
* Stacking production lines vertically saves real estate and limits horizontal travel distances.
* Use **Ceilings as Foundations** for the next level to keep height intervals uniform (usually 4m or 8m height per floor).

| Building Type | Footprint (Foundations) | Height Clearance | Preferred Placement |
| :--- | :--- | :--- | :--- |
| **Constructor** | 1.0 x 1.25 | 8 meters (2 walls) | Middle/Upper Floors |
| **Assembler** | 1.25 x 1.8 | 12 meters (3 walls) | Upper Floors |
| **Refinery** | 1.25 x 2.5 | 24 meters (6 walls) | Ground Floor / Outdoors |
| **Manufacturer**| 2.25 x 2.5 | 16 meters (4 walls) | Specialized top floors |

---

## 🤖 3. Bot Automation & Visual Strategies

These layout rules enable the vision and control bot to operate safely and effectively:

### 📐 Foundation Snapping Alignment
* **Rule:** Never place a machine directly on natural terrain. The bot should always build on standard foundations.
* **snapping grid:** Snapping buildings to the global grid makes coordinate mapping predictable, ensuring player position vectors match building locations.

### 🔭 Aerial Visual Calibration
* **Lookout Towers:** The bot can use Lookout Towers to gain a high-angle, top-down perspective of the factory floor.
* **Camera Calibration:** Top-down view isolates template shapes, making matching algorithms for belts and mergers far more accurate than low-angle horizontal templates.

---

## 🗺️ 4. SundownKid's Alternate Recipe Rankings

The bot includes an interactive **Alternate Recipe Advisor** based on the community-standard rankings from SundownKid's Steam Guide (ID 3551739887).

### 🏆 Tier Classifications
* **S-Tier (Must-Have):**
  * **Compacted Coal** (`Schematic_Alternate_EnrichedCoal`): Required for advanced fuels.
  * **Diluted Fuel** (`Schematic_Alternate_DilutedFuel`): Boosts fuel output using water loops.
  * **Electrode Circuit Board** (`Schematic_Alternate_ElectrodeCircuitBoard`): Uses Heavy Oil Residue, bypassing metals.
  * **Fused Wire** (`Schematic_Alternate_FusedWire`): Drastically boosts Wire early on using copper + caterium.
  * **Heavy Encased Frame** (`Schematic_Alternate_HeavyModularFrame`): Replaces screws with concrete.
  * **Heavy Oil Residue** (`Schematic_Alternate_HeavyOilResidue`): Corner stone residue generation.
  * **Molded Steel Pipe** (`Schematic_Alternate_SteelPipe_Molded`): Resource-saving steel pipe recipe.
  * **Nitro Rocket Fuel** (`Schematic_Alternate_RocketFuel_Nitro`): Massively simplifies rocket fuel lines.
  * **Sloppy Alumina** (`Schematic_Alternate_SloppyAlumina`): More alumina solution with zero silica byproduct.
  * **Solid Steel Ingot** (`Schematic_Alternate_IngotSteel1`): Saves coal by using iron ingots.
* **A-Tier (Strong / Efficient):**
  * **Bolted Frame** (`Schematic_Alternate_BoltedFrame`): Best Modular Frame recipe late game.
  * **Coated Iron Plate** (`Schematic_Alternate_CoatedIronPlate`): High output plates using plastic.
  * **Crystal Computer** (`Schematic_Alternate_Computer2`): Bypasses screws/wire using quartz.
  * **Recycled Rubber / Plastic** (`Schematic_Alternate_RecycledRubber`, `Schematic_Alternate_Plastic1`): Loop multipliers.
  * **Rigor Motor** (`Schematic_Alternate_Motor1`): Uses Crystal Oscillators to replace stators/rotors.
  * **Steel Screw** (`Schematic_Alternate_Screw2`): High volume (260/min) screw production using steel beams.
  * **Wet Concrete** (`Schematic_Alternate_WetConcrete`): Generates massive concrete from nearby water nodes.
* **B-Tier (Broadly Good):**
  * **Caterium Wire** (`Schematic_Alternate_Wire2`): Good in places without copper supply.
  * **Cheap Silica** (`Schematic_Alternate_Silica`): High volume silica using limestone.
  * **Insulated Crystal Oscillator** (`Schematic_Alternate_CrystalOscillator`): High throughput oscillators.
  * **Pure Quartz Crystal** (`Schematic_Alternate_PureQuartzCrystal`): Refinery water loop for quartz crystals.
  * **Silicon Circuit Board** (`Schematic_Alternate_CircuitBoard2`): Silica based circuit boards.
  * **Steel Cast Plate** (`Schematic_Alternate_SteelCoatedPlate`): Decent early steel plate option.
  * **Steel Rotor** (`Schematic_Alternate_Rotor`): Helps phase out screws.
  * **Steeled Frame** (`Schematic_Alternate_ModularFrame`): Decent early frame recipe.
  * **Stitched Iron Plate** (`Schematic_Alternate_ReinforcedIronPlate1`): Easy early plates using wire.
* **F-Tier (Noob Traps):**
  * **Cast Screw** (`Schematic_Alternate_Screw`): Labeled as overrated; does not change screw material cost.
  * **Pure Aluminum Ingot** (`Schematic_Alternate_PureAluminumIngot`): Overrated; normal ingot recipe is higher yield.
  * **Alclad Casing** (`Schematic_Alternate_AlcladCasing`): Useless, requires complex copper ingot logistics.
