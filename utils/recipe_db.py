# Satisfactory 1.0+ Recipe Database

# Each item maps to a dict:
#   "default": The base game standard recipe
#   "best": The best-in-class alternate recipe (S/A/B/C tier)
# A recipe is defined as:
#   {
#       "name": str,
#       "machine": str,
#       "inputs": dict[str, float],   # items per minute
#       "outputs": dict[str, float],  # items per minute
#       "alternate": bool,
#       "schematic": str or None      # Schematic class name to check unlock status
#   }
RECIPES: dict[str, dict[str, dict]] = {
    # --- Raw Ores & Basic Inputs ---
    # These represent base raw extractors/miners.
    # To keep recursion clean, if a node requires raw ore/liquid, it stops there.
    
    # --- Ingots ---
    "Iron Ingot": {
        "default": {
            "name": "Iron Ingot",
            "machine": "Smelter",
            "inputs": {"Iron Ore": 30.0},
            "outputs": {"Iron Ingot": 30.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Pure Iron Ingot",
            "machine": "Refinery",
            "inputs": {"Iron Ore": 35.0, "Water": 20.0},
            "outputs": {"Iron Ingot": 65.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_PureIronIngot"
        }
    },
    "Copper Ingot": {
        "default": {
            "name": "Copper Ingot",
            "machine": "Smelter",
            "inputs": {"Copper Ore": 30.0},
            "outputs": {"Copper Ingot": 30.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Pure Copper Ingot",
            "machine": "Refinery",
            "inputs": {"Copper Ore": 15.0, "Water": 10.0},
            "outputs": {"Copper Ingot": 37.5},
            "alternate": True,
            "schematic": "Schematic_Alternate_PureCopperIngot"
        }
    },
    "Caterium Ingot": {
        "default": {
            "name": "Caterium Ingot",
            "machine": "Smelter",
            "inputs": {"Caterium Ore": 45.0},
            "outputs": {"Caterium Ingot": 15.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Pure Caterium Ingot",
            "machine": "Refinery",
            "inputs": {"Caterium Ore": 24.0, "Water": 24.0},
            "outputs": {"Caterium Ingot": 12.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_PureCateriumIngot"
        }
    },
    "Steel Ingot": {
        "default": {
            "name": "Steel Ingot",
            "machine": "Foundry",
            "inputs": {"Iron Ore": 45.0, "Coal": 45.0},
            "outputs": {"Steel Ingot": 45.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Solid Steel Ingot",
            "machine": "Foundry",
            "inputs": {"Iron Ingot": 40.0, "Coal": 40.0},
            "outputs": {"Steel Ingot": 60.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_IngotSteel1"
        }
    },
    "Aluminum Ingot": {
        "default": {
            "name": "Aluminum Ingot",
            "machine": "Foundry",
            "inputs": {"Aluminum Scrap": 90.0, "Silica": 30.0},
            "outputs": {"Aluminum Ingot": 60.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Aluminum Ingot",
            "machine": "Foundry",
            "inputs": {"Aluminum Scrap": 90.0, "Silica": 30.0},
            "outputs": {"Aluminum Ingot": 60.0},
            "alternate": False,
            "schematic": None
        }
    },
    
    # --- Basic Components ---
    "Compacted Coal": {
        "default": {
            "name": "Compacted Coal",
            "machine": "Assembler",
            "inputs": {"Coal": 25.0, "Sulfur": 25.0},
            "outputs": {"Compacted Coal": 25.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_EnrichedCoal"
        },
        "best": {
            "name": "Compacted Coal",
            "machine": "Assembler",
            "inputs": {"Coal": 25.0, "Sulfur": 25.0},
            "outputs": {"Compacted Coal": 25.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_EnrichedCoal"
        }
    },
    "Concrete": {
        "default": {
            "name": "Concrete",
            "machine": "Constructor",
            "inputs": {"Limestone": 45.0},
            "outputs": {"Concrete": 15.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Wet Concrete",
            "machine": "Refinery",
            "inputs": {"Limestone": 120.0, "Water": 100.0},
            "outputs": {"Concrete": 80.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_WetConcrete"
        }
    },
    "Silica": {
        "default": {
            "name": "Silica",
            "machine": "Constructor",
            "inputs": {"Raw Quartz": 15.0},
            "outputs": {"Silica": 37.5},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Cheap Silica",
            "machine": "Assembler",
            "inputs": {"Raw Quartz": 15.0, "Limestone": 25.0},
            "outputs": {"Silica": 26.25},
            "alternate": True,
            "schematic": "Schematic_Alternate_Silica"
        }
    },
    "Quartz Crystal": {
        "default": {
            "name": "Quartz Crystal",
            "machine": "Constructor",
            "inputs": {"Raw Quartz": 37.5},
            "outputs": {"Quartz Crystal": 22.5},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Pure Quartz Crystal",
            "machine": "Refinery",
            "inputs": {"Raw Quartz": 67.5, "Water": 37.5},
            "outputs": {"Quartz Crystal": 52.5},
            "alternate": True,
            "schematic": "Schematic_Alternate_PureQuartzCrystal"
        }
    },
    "Wire": {
        "default": {
            "name": "Wire",
            "machine": "Constructor",
            "inputs": {"Copper Ingot": 15.0},
            "outputs": {"Wire": 30.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Fused Wire",
            "machine": "Assembler",
            "inputs": {"Copper Ingot": 12.0, "Caterium Ingot": 3.0},
            "outputs": {"Wire": 90.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_FusedWire"
        }
    },
    "Quickwire": {
        "default": {
            "name": "Quickwire",
            "machine": "Constructor",
            "inputs": {"Caterium Ingot": 12.0},
            "outputs": {"Quickwire": 60.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Fused Quickwire",
            "machine": "Assembler",
            "inputs": {"Caterium Ingot": 7.5, "Copper Ingot": 37.5},
            "outputs": {"Quickwire": 90.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_FusedQuickwire"
        }
    },
    "Cable": {
        "default": {
            "name": "Cable",
            "machine": "Constructor",
            "inputs": {"Wire": 60.0},
            "outputs": {"Cable": 30.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Insulated Cable",
            "machine": "Assembler",
            "inputs": {"Wire": 45.0, "Rubber": 30.0},
            "outputs": {"Cable": 100.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_Cable1"
        }
    },
    "Steel Pipe": {
        "default": {
            "name": "Steel Pipe",
            "machine": "Constructor",
            "inputs": {"Steel Ingot": 30.0},
            "outputs": {"Steel Pipe": 20.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Molded Steel Pipe",
            "machine": "Constructor",
            "inputs": {"Steel Ingot": 30.0, "Concrete": 10.0},
            "outputs": {"Steel Pipe": 20.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_SteelPipe_Molded"
        }
    },
    "Steel Beam": {
        "default": {
            "name": "Steel Beam",
            "machine": "Constructor",
            "inputs": {"Steel Ingot": 60.0},
            "outputs": {"Steel Beam": 15.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Aluminum Beam",
            "machine": "Assembler",
            "inputs": {"Alclad Aluminum Sheet": 100.0, "Concrete": 125.0},
            "outputs": {"Steel Beam": 60.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_AluminumBeam"
        }
    },
    "Iron Rod": {
        "default": {
            "name": "Iron Rod",
            "machine": "Constructor",
            "inputs": {"Iron Ingot": 15.0},
            "outputs": {"Iron Rod": 15.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Aluminum Rod",
            "machine": "Constructor",
            "inputs": {"Aluminum Ingot": 30.0},
            "outputs": {"Iron Rod": 225.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_AluminumRod"
        }
    },
    "Screw": {
        "default": {
            "name": "Screw",
            "machine": "Constructor",
            "inputs": {"Iron Rod": 10.0},
            "outputs": {"Screw": 40.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Steel Screw",
            "machine": "Constructor",
            "inputs": {"Steel Beam": 5.0},
            "outputs": {"Screw": 260.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_Screw2"
        }
    },
    "Copper Sheet": {
        "default": {
            "name": "Copper Sheet",
            "machine": "Constructor",
            "inputs": {"Copper Ingot": 20.0},
            "outputs": {"Copper Sheet": 10.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Steamed Copper Sheet",
            "machine": "Refinery",
            "inputs": {"Copper Ingot": 22.5, "Water": 22.5},
            "outputs": {"Copper Sheet": 22.5},
            "alternate": True,
            "schematic": "Schematic_Alternate_SteamedCopperSheet"
        }
    },
    "Iron Plate": {
        "default": {
            "name": "Iron Plate",
            "machine": "Constructor",
            "inputs": {"Iron Ingot": 30.0},
            "outputs": {"Iron Plate": 20.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Coated Iron Plate",
            "machine": "Assembler",
            "inputs": {"Iron Ingot": 37.5, "Plastic": 7.5},
            "outputs": {"Iron Plate": 75.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_CoatedIronPlate"
        }
    },
    "Fabric": {
        "default": {
            "name": "Fabric",
            "machine": "Constructor",
            "inputs": {"Mycelia": 15.0},
            "outputs": {"Fabric": 15.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Polyester Fabric",
            "machine": "Refinery",
            "inputs": {"Polymer Resin": 30.0, "Water": 30.0},
            "outputs": {"Fabric": 30.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_PolyesterFabric"
        }
    },
    
    # --- Advanced Components ---
    "Reinforced Iron Plate": {
        "default": {
            "name": "Reinforced Iron Plate",
            "machine": "Assembler",
            "inputs": {"Iron Plate": 30.0, "Screw": 60.0},
            "outputs": {"Reinforced Iron Plate": 5.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Stitched Iron Plate",
            "machine": "Assembler",
            "inputs": {"Iron Plate": 18.75, "Wire": 37.5},
            "outputs": {"Reinforced Iron Plate": 5.625},
            "alternate": True,
            "schematic": "Schematic_Alternate_ReinforcedIronPlate1"
        }
    },
    "Modular Frame": {
        "default": {
            "name": "Modular Frame",
            "machine": "Assembler",
            "inputs": {"Reinforced Iron Plate": 3.0, "Iron Rod": 12.0},
            "outputs": {"Modular Frame": 2.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Bolted Frame",
            "machine": "Assembler",
            "inputs": {"Reinforced Iron Plate": 7.5, "Screw": 140.0},
            "outputs": {"Modular Frame": 5.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_BoltedFrame"
        }
    },
    "Heavy Modular Frame": {
        "default": {
            "name": "Heavy Modular Frame",
            "machine": "Manufacturer",
            "inputs": {"Modular Frame": 10.0, "Steel Pipe": 30.0, "Encased Industrial Beam": 10.0, "Screw": 200.0},
            "outputs": {"Heavy Modular Frame": 2.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Heavy Encased Frame",
            "machine": "Manufacturer",
            "inputs": {"Modular Frame": 7.5, "Encased Industrial Beam": 9.375, "Steel Pipe": 33.75, "Concrete": 20.625},
            "outputs": {"Heavy Modular Frame": 2.8125},
            "alternate": True,
            "schematic": "Schematic_Alternate_HeavyModularFrame"
        }
    },
    "Encased Industrial Beam": {
        "default": {
            "name": "Encased Industrial Beam",
            "machine": "Assembler",
            "inputs": {"Steel Beam": 24.0, "Concrete": 30.0},
            "outputs": {"Encased Industrial Beam": 6.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Encased Industrial Pipe",
            "machine": "Assembler",
            "inputs": {"Steel Pipe": 28.0, "Concrete": 20.0},
            "outputs": {"Encased Industrial Beam": 4.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_EncasedIndustrialBeam"
        }
    },
    "Rotor": {
        "default": {
            "name": "Rotor",
            "machine": "Assembler",
            "inputs": {"Iron Rod": 20.0, "Screw": 100.0},
            "outputs": {"Rotor": 4.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Steel Rotor",
            "machine": "Assembler",
            "inputs": {"Steel Pipe": 10.0, "Wire": 30.0},
            "outputs": {"Rotor": 5.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_Rotor"
        }
    },
    "Stator": {
        "default": {
            "name": "Stator",
            "machine": "Assembler",
            "inputs": {"Steel Pipe": 15.0, "Wire": 40.0},
            "outputs": {"Stator": 5.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Quickwire Stator",
            "machine": "Assembler",
            "inputs": {"Steel Pipe": 15.0, "Quickwire": 60.0},
            "outputs": {"Stator": 8.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_Stator"
        }
    },
    "Motor": {
        "default": {
            "name": "Motor",
            "machine": "Assembler",
            "inputs": {"Rotor": 10.0, "Stator": 10.0},
            "outputs": {"Motor": 5.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Rigor Motor",
            "machine": "Manufacturer",
            "inputs": {"Rotor": 3.75, "Stator": 3.75, "Crystal Oscillator": 1.25},
            "outputs": {"Motor": 7.5},
            "alternate": True,
            "schematic": "Schematic_Alternate_Motor1"
        }
    },
    "Circuit Board": {
        "default": {
            "name": "Circuit Board",
            "machine": "Assembler",
            "inputs": {"Copper Sheet": 15.0, "Plastic": 30.0},
            "outputs": {"Circuit Board": 7.5},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Electrode Circuit Board",
            "machine": "Assembler",
            "inputs": {"Petroleum Coke": 20.0, "Heavy Oil Residue": 20.0},
            "outputs": {"Circuit Board": 15.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_ElectrodeCircuitBoard"
        }
    },
    "Computer": {
        "default": {
            "name": "Computer",
            "machine": "Manufacturer",
            "inputs": {"Circuit Board": 10.0, "Cable": 9.0, "Plastic": 18.0, "Screw": 52.0},
            "outputs": {"Computer": 2.5},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Crystal Computer",
            "machine": "Assembler",
            "inputs": {"Circuit Board": 7.5, "Crystal Oscillator": 2.5},
            "outputs": {"Computer": 2.8125},
            "alternate": True,
            "schematic": "Schematic_Alternate_Computer2"
        }
    },
    "Supercomputer": {
        "default": {
            "name": "Supercomputer",
            "machine": "Manufacturer",
            "inputs": {"Computer": 3.75, "AI Limiter": 3.75, "High-Speed Connector": 7.5, "Plastic": 56.25},
            "outputs": {"Supercomputer": 1.875},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "OC Supercomputer",
            "machine": "Manufacturer",
            "inputs": {"Computer": 3.0, "Electromagnetic Control Rod": 2.4, "Radio Control Unit": 4.8, "Quickwire": 36.0},
            "outputs": {"Supercomputer": 3.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_OCSupercomputer"
        }
    },
    "Radio Control Unit": {
        "default": {
            "name": "Radio Control Unit",
            "machine": "Manufacturer",
            "inputs": {"Aluminum Casing": 32.5, "Crystal Oscillator": 1.25, "Computer": 1.25},
            "outputs": {"Radio Control Unit": 2.5},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Radio Control System",
            "machine": "Assembler",
            "inputs": {"Aluminum Casing": 15.0, "Crystal Oscillator": 0.75},
            "outputs": {"Radio Control Unit": 1.5},
            "alternate": True,
            "schematic": "Schematic_Alternate_RadioControlSystem"
        }
    },
    "Crystal Oscillator": {
        "default": {
            "name": "Crystal Oscillator",
            "machine": "Manufacturer",
            "inputs": {"Quartz Crystal": 18.0, "Cable": 14.0, "Reinforced Iron Plate": 2.5},
            "outputs": {"Crystal Oscillator": 1.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Insulated Crystal Oscillator",
            "machine": "Manufacturer",
            "inputs": {"Quartz Crystal": 18.75, "Rubber": 18.75, "AI Limiter": 7.5},
            "outputs": {"Crystal Oscillator": 1.875},
            "alternate": True,
            "schematic": "Schematic_Alternate_CrystalOscillator"
        }
    },
    "Heat Sink": {
        "default": {
            "name": "Heat Sink",
            "machine": "Assembler",
            "inputs": {"Alclad Aluminum Sheet": 37.5, "Copper Sheet": 37.5},
            "outputs": {"Heat Sink": 7.5},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Heat Exchanger",
            "machine": "Assembler",
            "inputs": {"Aluminum Casing": 30.0, "Rubber": 30.0},
            "outputs": {"Heat Sink": 10.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_HeatExchanger"
        }
    },
    "AI Limiter": {
        "default": {
            "name": "AI Limiter",
            "machine": "Assembler",
            "inputs": {"Copper Sheet": 25.0, "Quickwire": 100.0},
            "outputs": {"AI Limiter": 5.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Plastic AI Limiter",
            "machine": "Assembler",
            "inputs": {"Copper Sheet": 22.5, "Quickwire": 90.0, "Plastic": 4.5},
            "outputs": {"AI Limiter": 5.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_AILimiter_Plastic"
        }
    },
    "Electromagnetic Control Rod": {
        "default": {
            "name": "Electromagnetic Control Rod",
            "machine": "Assembler",
            "inputs": {"Stator": 3.0, "AI Limiter": 4.0},
            "outputs": {"Electromagnetic Control Rod": 4.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Electromagnetic Control Rod",
            "machine": "Assembler",
            "inputs": {"Stator": 3.0, "AI Limiter": 4.0},
            "outputs": {"Electromagnetic Control Rod": 4.0},
            "alternate": False,
            "schematic": None
        }
    },
    
    # --- Aluminum Line ---
    "Aluminum Scrap": {
        "default": {
            "name": "Aluminum Scrap",
            "machine": "Refinery",
            "inputs": {"Alumina Solution": 240.0, "Coal": 120.0},
            "outputs": {"Aluminum Scrap": 360.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Electrode Aluminum Scrap",
            "machine": "Refinery",
            "inputs": {"Alumina Solution": 180.0, "Petroleum Coke": 60.0},
            "outputs": {"Aluminum Scrap": 300.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_ElectroAluminumScrap"
        }
    },
    "Alumina Solution": {
        "default": {
            "name": "Alumina Solution",
            "machine": "Refinery",
            "inputs": {"Bauxite": 120.0, "Water": 180.0},
            "outputs": {"Alumina Solution": 120.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Sloppy Alumina",
            "machine": "Refinery",
            "inputs": {"Bauxite": 120.0, "Water": 180.0},
            "outputs": {"Alumina Solution": 240.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_SloppyAlumina"
        }
    },
    "Alclad Aluminum Sheet": {
        "default": {
            "name": "Alclad Aluminum Sheet",
            "machine": "Assembler",
            "inputs": {"Aluminum Ingot": 30.0, "Copper Ingot": 10.0},
            "outputs": {"Alclad Aluminum Sheet": 30.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Alclad Aluminum Sheet",
            "machine": "Assembler",
            "inputs": {"Aluminum Ingot": 30.0, "Copper Ingot": 10.0},
            "outputs": {"Alclad Aluminum Sheet": 30.0},
            "alternate": False,
            "schematic": None
        }
    },
    "Aluminum Casing": {
        "default": {
            "name": "Aluminum Casing",
            "machine": "Constructor",
            "inputs": {"Aluminum Ingot": 90.0},
            "outputs": {"Aluminum Casing": 60.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Aluminum Casing",
            "machine": "Constructor",
            "inputs": {"Aluminum Ingot": 90.0},
            "outputs": {"Aluminum Casing": 60.0},
            "alternate": False,
            "schematic": None
        }
    },
    
    # --- Space Elevator & Late-game ---
    "Thermal Propulsion Rocket": {
        "default": {
            "name": "Thermal Propulsion Rocket",
            "machine": "Manufacturer",
            "inputs": {"Modular Engine": 2.5, "Turbo Motor": 1.0, "Cooling System": 1.25, "Fused Modular Frame": 1.25},
            "outputs": {"Thermal Propulsion Rocket": 1.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Thermal Propulsion Rocket",
            "machine": "Manufacturer",
            "inputs": {"Modular Engine": 2.5, "Turbo Motor": 1.0, "Cooling System": 1.25, "Fused Modular Frame": 1.25},
            "outputs": {"Thermal Propulsion Rocket": 1.0},
            "alternate": False,
            "schematic": None
        }
    },
    "Modular Engine": {
        "default": {
            "name": "Modular Engine",
            "machine": "Manufacturer",
            "inputs": {"Motor": 2.0, "Rubber": 15.0, "Smart Plating": 2.0},
            "outputs": {"Modular Engine": 1.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Modular Engine",
            "machine": "Manufacturer",
            "inputs": {"Motor": 2.0, "Rubber": 15.0, "Smart Plating": 2.0},
            "outputs": {"Modular Engine": 1.0},
            "alternate": False,
            "schematic": None
        }
    },
    "Smart Plating": {
        "default": {
            "name": "Smart Plating",
            "machine": "Assembler",
            "inputs": {"Reinforced Iron Plate": 2.0, "Rotor": 2.0},
            "outputs": {"Smart Plating": 2.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Plastic Smart Plating",
            "machine": "Assembler",
            "inputs": {"Reinforced Iron Plate": 1.5, "Rotor": 1.5, "Plastic": 3.0},
            "outputs": {"Smart Plating": 2.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_PlasticSmartPlating"
        }
    },
    "Cooling System": {
        "default": {
            "name": "Cooling System",
            "machine": "Blender",
            "inputs": {"Heat Sink": 15.0, "Rubber": 10.0, "Water": 10.0},
            "outputs": {"Cooling System": 7.5},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Cooling System",
            "machine": "Blender",
            "inputs": {"Heat Sink": 15.0, "Rubber": 10.0, "Water": 10.0},
            "outputs": {"Cooling System": 7.5},
            "alternate": False,
            "schematic": None
        }
    },
    "Fused Modular Frame": {
        "default": {
            "name": "Fused Modular Frame",
            "machine": "Blender",
            "inputs": {"Heavy Modular Frame": 1.0, "Aluminum Casing": 50.0, "Nitrogen Gas": 25.0},
            "outputs": {"Fused Modular Frame": 1.5},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Fused Modular Frame",
            "machine": "Blender",
            "inputs": {"Heavy Modular Frame": 1.0, "Aluminum Casing": 50.0, "Nitrogen Gas": 25.0},
            "outputs": {"Fused Modular Frame": 1.5},
            "alternate": False,
            "schematic": None
        }
    },
    "Turbo Motor": {
        "default": {
            "name": "Turbo Motor",
            "machine": "Manufacturer",
            "inputs": {"Motor": 4.0, "Radio Control Unit": 2.0, "Cooling System": 4.0, "Rubber": 25.0},
            "outputs": {"Turbo Motor": 1.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Turbo Pressure Motor",
            "machine": "Manufacturer",
            "inputs": {"Motor": 7.5, "Pressure Conversion Cube": 1.875, "Packaged Nitrogen Gas": 45.0, "Stator": 15.0},
            "outputs": {"Turbo Motor": 3.75},
            "alternate": True,
            "schematic": "Schematic_Alternate_TurboPressureMotor"
        }
    },
    "Packaged Nitrogen Gas": {
        "default": {
            "name": "Packaged Nitrogen Gas",
            "machine": "Packager",
            "inputs": {"Nitrogen Gas": 60.0, "Empty Canister": 60.0},
            "outputs": {"Packaged Nitrogen Gas": 60.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Packaged Nitrogen Gas",
            "machine": "Packager",
            "inputs": {"Nitrogen Gas": 60.0, "Empty Canister": 60.0},
            "outputs": {"Packaged Nitrogen Gas": 60.0},
            "alternate": False,
            "schematic": None
        }
    },
    "Empty Canister": {
        "default": {
            "name": "Empty Canister",
            "machine": "Constructor",
            "inputs": {"Plastic": 30.0},
            "outputs": {"Empty Canister": 60.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Empty Canister",
            "machine": "Constructor",
            "inputs": {"Plastic": 30.0},
            "outputs": {"Empty Canister": 60.0},
            "alternate": False,
            "schematic": None
        }
    },
    "Pressure Conversion Cube": {
        "default": {
            "name": "Pressure Conversion Cube",
            "machine": "Assembler",
            "inputs": {"Fused Modular Frame": 1.0, "Radio Control Unit": 2.0},
            "outputs": {"Pressure Conversion Cube": 1.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Pressure Conversion Cube",
            "machine": "Assembler",
            "inputs": {"Fused Modular Frame": 1.0, "Radio Control Unit": 2.0},
            "outputs": {"Pressure Conversion Cube": 1.0},
            "alternate": False,
            "schematic": None
        }
    },
    "Dark Matter Crystal": {
        "default": {
            "name": "Dark Matter Crystal",
            "machine": "Converter",
            "inputs": {"Dark Matter Residue": 20.0, "SAM": 20.0},
            "outputs": {"Dark Matter Crystal": 10.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Dark Matter Trap",
            "machine": "Converter",
            "inputs": {"Dark Matter Residue": 20.0, "SAM": 10.0},
            "outputs": {"Dark Matter Crystal": 20.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_DarkMatterTrap"
        }
    },
    "Diamond": {
        "default": {
            "name": "Diamond",
            "machine": "Particle Accelerator",
            "inputs": {"Coal": 240.0},
            "outputs": {"Diamond": 30.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Oil-Based Diamonds",
            "machine": "Refinery",
            "inputs": {"Crude Oil": 120.0, "Coal": 120.0},
            "outputs": {"Diamond": 30.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_Diamond_OilBased"
        }
    },
    
    # --- Nuclear ---
    "Encased Uranium Cell": {
        "default": {
            "name": "Encased Uranium Cell",
            "machine": "Blender",
            "inputs": {"Uranium": 50.0, "Concrete": 15.0, "Sulfuric Acid": 40.0},
            "outputs": {"Encased Uranium Cell": 25.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Infused Uranium Cell",
            "machine": "Manufacturer",
            "inputs": {"Uranium": 25.0, "Silica": 15.0, "Sulfur": 20.0, "Quickwire": 75.0},
            "outputs": {"Encased Uranium Cell": 20.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_UraniumCell1"
        }
    },
    "Uranium Fuel Rod": {
        "default": {
            "name": "Uranium Fuel Rod",
            "machine": "Manufacturer",
            "inputs": {"Encased Uranium Cell": 40.0, "Electromagnetic Control Rod": 2.0, "Crystal Oscillator": 1.0},
            "outputs": {"Uranium Fuel Rod": 0.4},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Uranium Fuel Unit",
            "machine": "Manufacturer",
            "inputs": {"Encased Uranium Cell": 20.0, "Electromagnetic Control Rod": 1.2, "Crystal Oscillator": 0.6, "Quickwire": 40.0},
            "outputs": {"Uranium Fuel Rod": 0.6},
            "alternate": True,
            "schematic": "Schematic_Alternate_NuclearFuelRod1"
        }
    },
    
    # --- Petrochemical Loops ---
    "Plastic": {
        "default": {
            "name": "Plastic",
            "machine": "Refinery",
            "inputs": {"Crude Oil": 30.0},
            "outputs": {"Plastic": 20.0, "Heavy Oil Residue": 10.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Recycled Plastic Loop",
            "machine": "Refinery",
            "inputs": {"Crude Oil": 30.0, "Water": 80.0},
            "outputs": {"Plastic": 80.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_Plastic1"
        }
    },
    "Rubber": {
        "default": {
            "name": "Rubber",
            "machine": "Refinery",
            "inputs": {"Crude Oil": 30.0},
            "outputs": {"Rubber": 20.0, "Heavy Oil Residue": 10.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Recycled Rubber Loop",
            "machine": "Refinery",
            "inputs": {"Crude Oil": 30.0, "Water": 80.0},
            "outputs": {"Rubber": 80.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_RecycledRubber"
        }
    },
    "Fuel": {
        "default": {
            "name": "Fuel",
            "machine": "Refinery",
            "inputs": {"Crude Oil": 60.0},
            "outputs": {"Fuel": 40.0, "Polymer Resin": 30.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Diluted Fuel",
            "machine": "Refinery",
            "inputs": {"Heavy Oil Residue": 50.0, "Water": 100.0},
            "outputs": {"Fuel": 100.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_DilutedFuel"
        }
    },
    "Heavy Oil Residue": {
        "default": {
            "name": "Heavy Oil Residue",
            "machine": "Refinery",
            "inputs": {"Crude Oil": 30.0},
            "outputs": {"Heavy Oil Residue": 10.0, "Plastic": 20.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Heavy Oil Residue",
            "machine": "Refinery",
            "inputs": {"Crude Oil": 30.0},
            "outputs": {"Heavy Oil Residue": 40.0, "Polymer Resin": 20.0},
            "alternate": True,
            "schematic": "Schematic_Alternate_HeavyOilResidue"
        }
    },
    "Petroleum Coke": {
        "default": {
            "name": "Petroleum Coke",
            "machine": "Refinery",
            "inputs": {"Heavy Oil Residue": 40.0},
            "outputs": {"Petroleum Coke": 120.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Petroleum Coke",
            "machine": "Refinery",
            "inputs": {"Heavy Oil Residue": 40.0},
            "outputs": {"Petroleum Coke": 120.0},
            "alternate": False,
            "schematic": None
        }
    },
    "Polymer Resin": {
        "default": {
            "name": "Polymer Resin",
            "machine": "Refinery",
            "inputs": {"Crude Oil": 60.0},
            "outputs": {"Polymer Resin": 130.0, "Heavy Oil Residue": 20.0},
            "alternate": False,
            "schematic": None
        },
        "best": {
            "name": "Polymer Resin",
            "machine": "Refinery",
            "inputs": {"Crude Oil": 60.0},
            "outputs": {"Polymer Resin": 130.0, "Heavy Oil Residue": 20.0},
            "alternate": False,
            "schematic": None
        }
    }
}

# Item AWESOME Sink Point values
SINK_POINTS: dict[str, int] = {
    "Thermal Propulsion Rocket": 732956,
    "Assembly Director System": 543632,
    "Nuclear Pasta": 538976,
    "Turbo Motor": 240496,
    "Supercomputer": 99576,
    "Modular Frame": 408,
    "Rotor": 140,
    "Iron Plate": 6,
    "Reinforced Iron Plate": 120,
    "Steel Beam": 64,
    "Steel Pipe": 24,
    "Stator": 148,
    "Motor": 1520,
    "Circuit Board": 696,
    "Computer": 17200,
    "Radio Control Unit": 19600,
    "Crystal Oscillator": 6120,
    "AI Limiter": 920,
    "Uranium Fuel Rod": 44092,
}
