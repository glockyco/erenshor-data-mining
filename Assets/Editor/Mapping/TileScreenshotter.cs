using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.SceneManagement;

public class TileScreenshotter
{
    public class TileShotterSettings
    {
        public string OutputRoot { get; set; } = null;

        public float CameraHeight { get; set; } = 1000f;
        public int ZoomLevels { get; set; } = 3;
        public int OriginX { get; set; } = 0;
        public int OriginY { get; set; } = 0;
        public int BaseTilesX { get; set; } = 2;
        public int BaseTilesY { get; set; } = 2;
        public int TilePixelSize { get; set; } = 256;
        public float TileWorldSize { get; set; } = 256f;
        public Action<int> PreProcess { get; set; }
        public Action<int> PostProcess { get; set; }
    }

    private static readonly Dictionary<string, TileScreenshotter.TileShotterSettings> SceneConfigs =
        new Dictionary<string, TileScreenshotter.TileShotterSettings>
        {
            {
                "Abyssal", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = -40,
                    OriginY = -120,
                    BaseTilesX = 3,
                    BaseTilesY = 3,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                string[] objNames =
                                {
                                    "SM_Rock_Tile_03 (10)", "SM_Rock_Tile_03 (11)", "SM_Rock_Tile_03 (18)",
                                    "SM_Rock_Tile_03 (14)", "SM_Rock_Tile_03 (9)", "SM_Rock_Tile_03 (17)",
                                    "SM_Rock_Pile_04 (3)", "SM_Env_Cliff_Basalt_01 (129)", "SM_Rock_Tile_03 (13)",
                                    "SM_Rock_Tile_03 (12)", "SM_Rock_Tile_03 (16)", "SM_Rock_Tile_03 (15)",
                                    "SM_Rock_Pile_04 (2)", "SM_Rock_Pile_04", "SM_Rock_Pile_04 (1)",
                                    "SM_Rock_Tile_03 (6)", "SM_Rock_Tile_03 (5)", "SM_Rock_Tile_03 (4)",
                                    "SM_Rock_Tile_03 (3)", "SM_Rock_Tile_03", "SM_Rock_Tile_03 (1)",
                                    "SM_Rock_Tile_03 (2)", "SM_Env_Rock_Cave_01"
                                };
                                if (objNames.Contains(obj.name))
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                    }
                }
            },
            {
                "Azure", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = -32,
                    OriginY = 0,
                    BaseTilesX = 2,
                    BaseTilesY = 3,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 1)
                        {
                            string[] objNames =
                            {
                                "SM_Tree_Pine_Small_01 (3)",
                                "SM_Tree_Pine_Small_01 (4)",
                                "SM_Tree_Pine_Small_01 (5)",
                            };
                            foreach (var objName in objNames)
                            {
                                var obj = GameObject.Find(objName);
                                obj?.SetActive(false);
                            }
                        }
                    }
                }
            },
            {
                "Azynthi", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = 145,
                    OriginY = 130,
                    BaseTilesX = 3,
                    BaseTilesY = 3,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            var obj = GameObject.Find("SM_Tree_Generic_Giant_01_LOD_01 (1)");
                            obj?.SetActive(false);
                        }
                        else if (zoomLevel == 1)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (obj.transform.position.x > 650f || obj.transform.position.y < 115f) continue;
                                if (!obj.name.StartsWith("SM_") && !obj.name.ToLower().Contains("torch") && !obj.name.ToLower().Contains("fire")) continue;
                                if (obj.name.StartsWith("SM_Bld_Base_Floor_Combined")) continue;
                                
                                obj.SetActive(false);
                            }
                        }
                        else if (zoomLevel == 3)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (obj.transform.position.x > 650f || obj.transform.position.y < 105f) continue;
                                if (!obj.name.StartsWith("SM_") && !obj.name.ToLower().Contains("torch") && !obj.name.ToLower().Contains("fire")) continue;
                                
                                obj.SetActive(false);
                            }
                        }
                    }
                }
            },
            {
                "AzynthiClear", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = 145,
                    OriginY = 130,
                    BaseTilesX = 3,
                    BaseTilesY = 3,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            var obj = GameObject.Find("SM_Tree_Generic_Giant_01_LOD_01 (1)");
                            obj?.SetActive(false);
                        }
                        else if (zoomLevel == 1)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (obj.transform.position.x > 650f || obj.transform.position.y < 115f) continue;
                                if (!obj.name.StartsWith("SM_") && !obj.name.ToLower().Contains("torch") && !obj.name.ToLower().Contains("fire")) continue;
                                if (obj.name.StartsWith("SM_Bld_Base_Floor_Combined")) continue;
                                
                                obj.SetActive(false);
                            }
                        }
                        else if (zoomLevel == 3)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (obj.transform.position.x > 650f || obj.transform.position.y < 105f) continue;
                                if (!obj.name.StartsWith("SM_") && !obj.name.ToLower().Contains("torch") && !obj.name.ToLower().Contains("fire")) continue;
                                
                                obj.SetActive(false);
                            }
                        }
                    }
                }
            },
            {
                "Blight", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 3,
                    BaseTilesX = 4,
                    BaseTilesY = 4,
                }
            },
            {
                "Bonepits", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = -128,
                    OriginY = 64,
                    BaseTilesX = 2,
                    BaseTilesY = 2,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                string[] objNames =
                                {
                                    "rock3 (6)", "rock3", "rock2 (1)", "rock2", "rock3 (1)", "rock2 (2)", "rock2 (21)",
                                    "rock2 (20)", "SM_Env_Cave_01 (20)", "SM_Env_Cave_01 (18)", "SM_Env_Cave_01 (19)",
                                    "rock2 (3)", "SM_Env_Cave_Large_01 (5)", "rock3 (4)", "rock2 (4)", "rock2 (6)",
                                    "rock2 (7)", "rock2 (8)", "rock2 (22)", "rock2 (19)", "rock2 (33)", "rock2 (35)",
                                    "rock2 (5)", "rock2 (34)", "rock2 (15)", "SM_Env_Cave_Large_01_DoubleSided (12)",
                                    "SM_Env_Cave_Large_01_DoubleSided (4)", "rock2 (9)", "rock2 (13)", "rock2 (14)",
                                    "rock2 (27)", "rock2 (28)", "rock2 (29)", "rock2 (30)", "rock2 (31)", "rock4 (20)",
                                    "rock2 (12)", "SM_Env_Cave_Background_01_DoubleSided (18)", "rock4 (10)",
                                    "SM_Env_Cave_Large_01 (12)", "rock2 (26)", "rock4 (11)", "rock2 (25)",
                                    "rock2 (32)", "SM_Env_Cave_Background_01_DoubleSided (4)",
                                };
                                if (objNames.Contains(obj.name))
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                    }
                }
            },
            {
                "Brake", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 3,
                    BaseTilesX = 2,
                    BaseTilesY = 2,
                }
            },
            {
                "Braxonia", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = 40,
                    OriginY = 80,
                    BaseTilesX = 3,
                    BaseTilesY = 3,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            string[] objNames =
                            {
                                "SM_Bld_Castle_Wall_Cut_02 (370)", "SM_Bld_Castle_Wall_Cut_02 (753)", "SM_Bld_Castle_Wall_Cut_02 (371)",
                                "SM_Bld_Castle_Wall_Cut_02 (68)", "SM_Prop_Light_Chandelier_02", "SM_Bld_Castle_Wall_Cut_02 (248)",
                                "SM_Bld_Castle_Wall_Cut_02 (250)", "SM_Bld_Castle_Wall_Cut_02 (249)", "SM_Bld_House_Railing_Beam_01 (17)",
                                "SM_Bld_Castle_Wall_Cut_02 (242)", "SM_Bld_Castle_Wall_Cut_02 (247)", "SM_Bld_Castle_Wall_Cut_02 (237)",
                                "SM_Bld_House_Railing_Beam_01 (16)", "SM_Bld_Castle_Wall_Cut_02 (462)", "SM_Bld_Castle_Wall_Cut_02 (463)",
                                "SM_Bld_Castle_Wall_Cut_02 (464)", "SM_Bld_Wall_Beam_01 (3)", "SM_Bld_Wall_Beam_01 (4)",
                                "SM_Bld_Castle_Wall_Cut_02 (245)", "SM_Bld_House_Railing_Beam_01 (14)", "SM_Bld_Castle_Wall_Cut_02 (246)",
                                "SM_Bld_House_Railing_Beam_01 (15)", "SM_Bld_Castle_Wall_Cut_02 (679)", "SM_Bld_House_Railing_Beam_01 (36)",
                                "SM_Bld_Castle_Wall_Cut_02 (680)", "SM_Bld_House_Railing_Beam_01 (35)", "SM_Bld_House_Railing_Beam_01 (34)",
                                "SM_Bld_House_Railing_Beam_01 (33)", "SM_Bld_Castle_Wall_Cut_02 (752)", "SM_Bld_Castle_Wall_Cut_02 (751)",
                                "SM_Bld_Castle_Wall_Cut_02 (287)", "SM_Bld_Castle_Wall_Cut_02 (309)", "SM_Bld_Castle_Wall_Cut_02 (286)",
                                "SM_Bld_House_Railing_Beam_01 (21)", "SM_Bld_Castle_Wall_Cut_02 (285)", "SM_Bld_Castle_Wall_Cut_02 (278)",
                                "SM_Bld_Castle_Wall_Cut_02 (307)", "SM_Bld_House_Railing_Beam_01 (20)", "SM_Bld_House_Railing_Beam_01 (18)",
                                "SM_Bld_House_Railing_Beam_01 (19)", "SM_Bld_Castle_Wall_Cut_02 (284)", "SM_Bld_Castle_Wall_Cut_02 (308)",
                                "SM_Prop_Light_Chandelier_02 (1)", "SM_Bld_Castle_Wall_Cut_02 (487)", "SM_Bld_Castle_Wall_Cut_02 (488)",
                                "SM_Bld_Castle_Wall_Cut_02 (489)", "SM_Bld_Castle_Wall_Cut_02 (490)", "SM_Bld_Castle_Wall_Cut_02 (491)",
                                "SM_Bld_Wall_Beam_01 (2)", "SM_Bld_Wall_Beam_01 (1)", "SM_Bld_Wall_Beam_01",
                                "SM_Prop_Light_Chandelier_02 (4)", "SM_Prop_Light_Chandelier_02 (3)", "SM_Prop_Light_Chandelier_02 (2)",
                                "SM_Bld_Castle_Wall_Cut_03 (319)", "SM_Bld_Castle_Wall_Cut_03 (320)", "SM_Bld_Castle_Wall_Cut_03 (321)",
                                "SM_Bld_Castle_Wall_Cut_03 (322)", "SM_Bld_Castle_Wall_Cut_03 (323)", "SM_Bld_Castle_Wall_Cut_03 (324)",
                                "SM_Bld_Castle_Wall_Cut_03 (325)", "SM_Bld_Castle_Wall_Cut_03 (326)", "SM_Bld_Castle_Wall_Cut_03 (327)",
                                "SM_Bld_Castle_Wall_Cut_03 (328)", "SM_Bld_Castle_Wall_Cut_03 (329)", "SM_Bld_Castle_Wall_Cut_03 (330)",
                                "SM_Bld_Castle_Wall_Cut_02 (205)", "SM_Bld_Castle_Wall_Cut_02 (206)", "SM_Bld_Castle_Wall_Cut_02 (204)",
                                "SM_Bld_Castle_Wall_Cut_02 (207)", "SM_Bld_Castle_Wall_Cut_02 (203)", "SM_Bld_Castle_Wall_Cut_02 (202)",
                                "SM_Bld_Castle_Wall_Cut_02 (201)", "SM_Bld_Castle_Wall_Cut_02 (208)", "SM_Bld_Castle_Wall_Cut_02 (597)",
                                "SM_Bld_Castle_Wall_Cut_02 (598)", "SM_Bld_Castle_Wall_Cut_02 (599)", "SM_Bld_Castle_Wall_Cut_02 (594)",
                                "SM_Bld_Castle_Wall_Cut_02 (595)", "SM_Bld_Castle_Wall_Cut_02 (596)", "SM_Bld_Castle_Wall_Cut_02 (591)",
                                "SM_Bld_Castle_Wall_Cut_02 (592)", "SM_Bld_Castle_Wall_Cut_02 (593)", "SM_Bld_Castle_Wall_Cut_02 (609)",
                                "SM_Bld_Castle_Wall_Cut_02 (602)", "SM_Bld_Castle_Wall_Cut_02 (601)", "SM_Bld_Castle_Wall_Cut_02 (600)",
                                "SM_Bld_Castle_Wall_Cut_02 (605)", "SM_Bld_Castle_Wall_Cut_02 (604)", "SM_Bld_Castle_Wall_Cut_02 (603)",
                                "SM_Bld_Castle_Wall_Cut_02 (606)", "SM_Bld_Castle_Wall_Cut_02 (607)", "SM_Bld_Castle_Wall_Cut_02 (608)",
                                "SM_Bld_Castle_Wall_Cut_02 (610)", "SM_Bld_Wall_Beam_01 (42)", "SM_Bld_Wall_Beam_01 (40)",
                                "SM_Bld_Wall_Beam_01 (38)", "SM_Bld_Wall_Beam_01 (39)", "SM_Bld_Wall_Beam_01 (37)",
                                "SM_Bld_Wall_Beam_01 (36)", "SM_Bld_Wall_Beam_01 (41)", "SM_Bld_Wall_Beam_01 (7)",
                                "SM_Bld_Wall_Beam_01 (35)", "SM_Bld_Wall_Beam_01 (34)", "SM_Bld_Wall_Beam_01 (33)",
                                "SM_Bld_Wall_Beam_01 (32)", "SM_Bld_Castle_Wall_Cut_02 (426)", "SM_Bld_Castle_Wall_Cut_02 (427)",
                                "SM_Bld_Castle_Wall_Cut_02 (428)", "SM_Bld_Wall_Beam_01 (5)", "SM_Bld_Wall_Beam_01 (6)",
                                "SM_Env_Tiles_07 (91)", "SM_Bld_Castle_Wall_Cut_02 (293)", "SM_Bld_Castle_Wall_Cut_02 (311)",
                                "SM_Bld_Castle_Wall_Cut_02 (310)", "SM_Bld_Castle_Wall_Cut_02 (292)",
                                "SM_Env_Tiles_07 (246)", "SM_Env_Tiles_07 (202)", "SM_Env_Tiles_07 (245)",
                                "SM_Env_Tiles_07 (196)", "SM_Bld_Castle_Wall_Cut_02 (545)", "SM_Bld_Castle_Wall_Cut_02 (544)",
                                "SM_Bld_Castle_Wall_Cut_02 (562)", "SM_Bld_Castle_Wall_Cut_02 (563)", "SM_Env_Tiles_07 (198)",
                                "SM_Env_Tiles_07 (244)", "SM_Env_Tiles_07 (247)", "SM_Env_Tiles_07 (195)",
                                // Lower layer ceilings:
                                "SM_Env_Rock_Flat_03 (6)", "SM_Env_Rock_Flat_03 (11)", "SM_Env_Rock_Flat_03 (5)",
                                "SM_Env_Rock_Flat_03 (4)", "SM_Env_Rock_Flat_02 (6)", "SM_Env_Rock_Flat_02 (4)",
                                "SM_Env_Rock_Flat_02 (3)", "SM_Env_Rock_Flat_02 (1)", "SM_Env_Rock_Flat_02 (5)",
                                "SM_Env_Rock_Flat_03 (7)", "SM_Env_Rock_Flat_02 (2)", "SM_Env_Rock_Flat_03 (8)",
                                "SM_Env_Rock_Flat_03 (2)", "SM_Env_Rock_Flat_02", "SM_Env_Rock_Flat_03 (9)",
                                "SM_Env_Rock_Flat_03 (1)", "SM_Env_Rock_Flat_03", "SM_Env_Rock_Flat_03 (3)",
                                "SM_Env_Rock_Flat_03 (10)", "SM_Env_Rock_Pile_01", "SM_Env_Rock_Pile_01 (1)",
                                "SM_Env_Rock_Pile_01 (2)", "SM_Env_Rock_Cliff_03 (31)",
                            };
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (obj.name.Contains("SM_Env_Tiles_09") || obj.name.Contains("SM_Env_Wall_Curved_Roof_01"))
                                {
                                    obj.SetActive(false);
                                }
                                else if (objNames.Contains(obj.name))
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                        // else if (zoomLevel == 2)
                        // {
                        //     string[] objNames =
                        //     {
                        //         "SM_Bld_Castle_Wall_Cut_02 (589)", "SM_Bld_Castle_Wall_Cut_02 (590)", "SM_Bld_Castle_Wall_Cut_02 (586)",
                        //         "SM_Bld_Castle_Wall_Cut_02 (587)", "SM_Bld_Castle_Wall_Cut_02 (585)", "SM_Bld_Castle_Wall_Cut_02 (584)",
                        //         "SM_Bld_Castle_Wall_Cut_02 (583)", "SM_Bld_Castle_Wall_Cut_02 (582)", "SM_Bld_Castle_Wall_Cut_02 (588)",
                        //         "SM_Env_Rock_Flat_03 (8)", "SM_Env_Rock_Pile_01 (2)", "SM_Env_Rock_Pile_01 (1)",
                        //         "SM_Env_Rock_Pile_01", "SM_Env_Rock_Cliff_03 (31)", "SM_Bld_Castle_Pillar_Stone_04 (38)",
                        //         "SM_Bld_Castle_Roof_M_Curved_End_Beam_01 (2)", "SM_Bld_Castle_Roof_M_Curved_End_Beam_01",
                        //         "SM_Bld_Castle_Pillar_Stone_04 (39)", "SM_Bld_Castle_Roof_M_Curved_End_Beam_01 (3)",
                        //         "SM_Bld_Castle_Roof_M_Curved_End_Beam_01 (1)", "SM_Bld_Beam_01 (22)", "SM_Bld_Beam_01 (23)",
                        //         "SM_Bld_Beam_01 (10)", "SM_Bld_Beam_01 (9)", "SM_Bld_Beam_01 (8)",
                        //     };
                        //     foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                        //     {
                        //         if (obj.transform.position.y > 57f)
                        //         {
                        //             obj.SetActive(false);
                        //         }
                        //         else if (obj.transform.position.y > 44f && obj.transform.position.z < 510f)
                        //         {
                        //             obj.SetActive(false);
                        //         }
                        //         else if (objNames.Contains(obj.name))
                        //         {
                        //             obj.SetActive(false);
                        //         }
                        //     }
                        // }
                    }
                }
            },
            {
                "Braxonian", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = -128,
                    OriginY = 0,
                    BaseTilesX = 5,
                    BaseTilesY = 6,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 1)
                        {
                            string[] objNames =
                            {
                                "SM_Env_Rock_Cliff_03 (51)",
                                "SM_Env_Rock_Cliff_03 (65)",
                            };
                            foreach (var objName in objNames)
                            {
                                var obj = GameObject.Find(objName);
                                obj?.SetActive(false);
                            }
                        }
                    }
                }
            },
            {
                "Duskenlight", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = 0,
                    OriginY = 0,
                    BaseTilesX = 7,
                    BaseTilesY = 4,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            var obj = GameObject.Find("SM_Env_Rock_Cliff_03 (58)");
                            obj?.SetActive(false);
                        }
                    }
                }
            },
            {
                "Elderstone", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = -1100,
                    OriginY = -1150,
                    BaseTilesX = 7,
                    BaseTilesY = 10,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                string[] objNames =
                                {
                                    "TFF_Rock_Large_03A (9)", "TFF_Rock_Large_03A (5)", "TFF_Rock_Large_03A (3)",
                                    "TFF_Rock_Large_01A (1)", "TFF_Rock_Large_03A (4)", "TFF_Rock_Large_06A (79)",
                                    "TFF_Rock_Large_03A (6)", "TFF_Rock_Large_03A (8)", "TFF_Rock_Large_03A (7)",
                                    "TFF_Rock_Large_03A (10)", "SM_Env_Stalagmite_03 (13)", "Rock_Large_03A (12)",
                                    "SM_Env_Stalagmite_05 (4)", "SM_Env_Stalagmite_05 (2)", "SM_Env_Stalagmite_05 (7)",
                                    "SM_Env_Stalagmite_05", "SM_Env_Stalagmite_05 (5)", "SM_Env_Stalagmite_05 (1)",
                                    "SM_Env_Stalagmite_05 (3)", "SM_Tree_Swamp_Stump_01 (2)", "SM_Tree_Swamp_Stump_01",
                                    "SM_Tree_Swamp_Stump_01 (1)", "SM_Tree_Swamp_Stump_01 (3)", "SM_Env_Stalagmite_05 (6)",
                                    "TFF_Rock_Large_03A (13)", "TFF_Rock_Large_01A", "TFF_Rock_Large_06A (80)",
                                    "TFF_Rock_Large_06A (83)", "TFF_Rock_Large_01A (4)", "TFF_Rock_Large_01A (3)",
                                    "TFF_Rock_Large_06A (23)", "TFF_Rock_Large_01A (2)", "TFF_Rock_Large_06A (98)",
                                    "TFF_Rock_Large_06A (70)", "TFF_Rock_Large_03A (12)", "TFF_Rock_Large_03A (15)",
                                    "TFF_Rock_Large_06A (88)"
                                };
                                if (objNames.Contains(obj.name))
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                    }
                }
            },
            {
                "FernallaField", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 3,
                    BaseTilesX = 6,
                    BaseTilesY = 6,
                }
            },
            {
                "Hidden", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = -200,
                    OriginY = -300,
                    BaseTilesX = 2,
                    BaseTilesY = 2,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            var obj = GameObject.Find("rock4 (25)");
                            obj?.SetActive(false);
                        }
                    }
                }
            },
            {
                "Jaws", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = 1050,
                    OriginY = -150,
                    BaseTilesX = 3,
                    BaseTilesY = 2,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            string[] objNames =
                            {
                                "SM_Env_Tiles_Ornate_01 (545)", "SM_Env_Tiles_Ornate_01 (550)", "SM_Env_Tiles_Ornate_01 (551)",
                                "SM_Env_Tiles_Ornate_01 (556)", "SM_Env_Tiles_Ornate_01 (558)", "SM_Env_Tiles_Ornate_01 (559)",
                                "SM_Env_Tiles_Ornate_01 (557)", "SM_Env_Tiles_Ornate_01 (560)", "SM_Env_Tiles_Ornate_01 (564)",
                                "SM_Env_Tiles_Ornate_01 (565)", "SM_Env_Tiles_Ornate_01 (573)", "SM_Env_Tiles_Ornate_01 (568)",
                                "SM_Env_Tiles_Ornate_01 (569)", "SM_Env_Tiles_Ornate_01 (570)", "SM_Env_Tiles_Ornate_01 (571)",
                                "SM_Env_Tiles_Ornate_01 (567)", "SM_Env_Tiles_Ornate_01 (566)", "SM_Env_Tiles_Ornate_01 (562)",
                                "SM_Env_Tiles_Ornate_01 (561)", "SM_Env_Tiles_Ornate_01 (563)", "SM_Env_Tiles_Ornate_01 (546)",
                                "SM_Env_Tiles_Ornate_01 (542)", "SM_Env_Tiles_Ornate_01 (548)", "SM_Env_Tiles_Ornate_01 (547)",
                                "SM_Env_Tiles_Ornate_01 (543)", "SM_Env_Tiles_Ornate_01 (544)", "SM_Env_Tiles_Ornate_01 (578)",
                                "SM_Env_Tiles_Ornate_01 (552)", "SM_Env_Tiles_Ornate_01 (553)", "SM_Env_Tiles_Ornate_01 (555)",
                                "SM_Env_Tiles_Ornate_01 (554)", "SM_Bld_Castle_Wall_01 (542)", "SM_Env_Tiles_Ornate_01 (579)",
                                "SM_Env_Tiles_Ornate_01 (580)", "SM_Env_Tiles_Ornate_01 (581)", "SM_Env_Tiles_Ornate_01 (582)",
                                "SM_Env_Tiles_Ornate_01 (583)", "SM_Env_Tiles_Ornate_01 (585)", "SM_Env_Tiles_Ornate_01 (584)",
                                "SM_Env_Tiles_Ornate_01 (587)", "SM_Env_Tiles_Ornate_01 (588)", "SM_Env_Tiles_Ornate_01 (594)",
                                "SM_Env_Tiles_Ornate_01 (595)", "SM_Env_Tiles_Ornate_01 (596)", "SM_Env_Tiles_Ornate_01 (597)",
                                "SM_Env_Tiles_Ornate_01 (465)", "SM_Env_Tiles_Ornate_01 (466)", "SM_Env_Tiles_Ornate_01 (461)",
                                "SM_Env_Tiles_Ornate_01 (470)", "SM_Env_Tiles_Ornate_01 (471)", "SM_Env_Tiles_Ornate_01 (474)",
                                "SM_Env_Tiles_Ornate_01 (572)", "SM_Env_Tiles_Ornate_01 (304)", "SM_Env_Tiles_Ornate_01 (303)",
                                "SM_Env_Tiles_Ornate_01 (352)", "SM_Env_Tiles_Ornate_01 (351)", "SM_Env_Tiles_Ornate_01 (363)",
                                "SM_Env_Tiles_Ornate_01 (364)", "SM_Env_Tiles_Ornate_01 (349)", "SM_Env_Tiles_Ornate_01 (350)",
                                "SM_Env_Tiles_Ornate_01 (361)", "SM_Env_Tiles_Ornate_01 (362)", "SM_Env_Tiles_Ornate_01 (394)",
                                "SM_Env_Tiles_Ornate_01 (395)", "SM_Env_Tiles_Ornate_01 (396)", "SM_Env_Tiles_Ornate_01 (398)",
                                "SM_Env_Tiles_Ornate_01 (397)", "SM_Env_Tiles_Ornate_01 (399)", "SM_Env_Tiles_Ornate_01 (400)",
                                "SM_Env_Tiles_Ornate_01 (131)", "SM_Env_Tiles_Ornate_01 (138)", "SM_Bld_Castle_Wall_01 (469)",
                                "SM_Bld_Castle_Wall_01 (470)", "SM_Bld_Castle_Wall_01 (471)", "SM_Bld_Castle_Wall_01 (472)",
                                "SM_Bld_Castle_Wall_01 (473)",
                            };
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (obj.name.Contains("SM_Env_Tiles_05") || obj.name.Contains("SM_Env_Tiles_07") || obj.name.Contains("SM_Bld_Wall_Beam_01"))
                                {
                                    obj.SetActive(false);
                                    continue;
                                }
                                // if (obj.transform.position.y > -10 && obj.transform.position.x > 1235)
                                // {
                                //     obj.SetActive(false);
                                //     continue;
                                // }
                                if (objNames.Contains(obj.name))
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                    }
                }
            },
            {
                "Krakengard", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 5,
                    OriginX = 250,
                    OriginY = 100,
                    BaseTilesX = 1,
                    BaseTilesY = 1,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            string[] objNames =
                            {
                                "SM_Bld_Castle_Floor_Stone_01 (66)",
                                "SM_Bld_Castle_Floor_Stone_01 (67)",
                                "SM_Bld_Castle_Floor_Stone_01 (27)",
                                "SM_Bld_Castle_Floor_Stone_01 (26)",
                                "SM_Bld_Castle_Floor_Stone_01 (28)",
                                "SM_Bld_Castle_Floor_Stone_01 (22)",
                                "SM_Bld_Castle_Floor_Stone_01 (21)",
                                "SM_Bld_Castle_Floor_Stone_01 (24)",
                                "SM_Bld_Castle_Floor_Stone_01 (23)",
                                "SM_Bld_Castle_Floor_Stone_01 (20)",
                                "SM_Bld_Castle_Floor_Stone_01 (25)",
                            };
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (objNames.Contains(obj.name))
                                {
                                    obj.SetActive(false);
                                }
                                if (obj.name.StartsWith("SM_Env_Basement_Ceiling_01"))
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                        // if (zoomLevel == 3)
                        // {
                        //     string[] objNames =
                        //     {
                        //         "SM_Bld_Castle_Wall_Cut_01 (273)",
                        //         "SM_Bld_Castle_Wall_Cut_01 (276)",
                        //     };
                        //     foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                        //     {
                        //         if (objNames.Contains(obj.name))
                        //         {
                        //             obj.SetActive(false);
                        //         }
                        //         if (obj.name.StartsWith("SM_") && obj.transform.position.x < 400f && obj.transform.position.y > 54f)
                        //         {
                        //             obj.SetActive(false);
                        //         }
                        //     }
                        // }
                    }
                }
            },
            {
                "Loomingwood", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 3,
                    BaseTilesX = 4,
                    BaseTilesY = 4,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            string[] objNames =
                            {
                                "SM_Env_Tree_Giant_01_LOD2 (35)", "SM_Env_Tree_Giant_01_LOD2 (36)",
                                "SM_Env_Tree_Giant_01_LOD2 (37)", "SM_Env_Tree_Giant_01_LOD2 (38)",
                                "SM_Env_Tree_Giant_01_LOD2 (39)", "SM_Env_Rock_Cliff_03 (75)",
                                "SM_Env_Rock_Cliff_03 (70)", "SM_Env_Rock_Cliff_03 (68)",
                                "SM_Env_Rock_Cliff_03 (71)", "SM_Env_Rock_Cliff_03 (72)",
                                "SM_Env_Rock_Cliff_03 (69)", "SM_Env_Rock_Cliff_03 (79)",
                                "SM_Env_Rock_Cliff_03 (81)",
                            };
                            foreach (var objName in objNames)
                            {
                                var obj = GameObject.Find(objName);
                                obj?.SetActive(false);
                            }
                        }
                        else if (zoomLevel == 1)
                        {
                            var allGameObjects = UnityEngine.Object.FindObjectsOfType<GameObject>();
                            foreach (var go in allGameObjects)
                            {
                                var name = go.name.ToLower();
                                if (name.Contains("tree_giant"))
                                {
                                    go.SetActive(false);
                                }
                            }
                        }
                    }
                }
            },
            {
                "Malaroth", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = 0,
                    OriginY = 0,
                    BaseTilesX = 5,
                    BaseTilesY = 4,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            string[] objNames =
                            {
                                "SM_Env_Dirt_Cliff_06 (31)",
                                "SM_Env_Dirt_Cliff_06 (25)",
                                "SM_Env_Dirt_Cliff_06 (28)",
                                "SM_Env_Dirt_Cliff_06 (26)",
                                "SM_Env_Dirt_Cliff_06 (27)",
                                "SM_Env_Rock_Cliff_01 (23)",
                                "SM_Env_Dirt_Cliff_06 (30)",
                            };
                            foreach (var objName in objNames)
                            {
                                var obj = GameObject.Find(objName);
                                obj?.SetActive(false);
                            }
                        }
                    }
                }
            },
            {
                "PrielPlateau", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = 0,
                    OriginY = 0,
                    BaseTilesX = 3,
                    BaseTilesY = 3,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                string[] objNames =
                                {
                                    "TFF_Rock_Large_06A_LOD_1 (29)",
                                    "TFF_Rock_Large_06A_LOD_1 (30)",
                                    "TFF_Rock_Large_06A_LOD_1 (60)",
                                    "TFF_Rock_Large_06A_LOD_1 (59)",
                                    "TFF_Rock_Large_06A_LOD_1 (39)",
                                };
                                if (objNames.Contains(obj.name))
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                        else if (zoomLevel == 2)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                string[] objNames =
                                {
                                    "TFF_Pine_Tree_02C_LOD_1",
                                    "TFF_Pine_Tree_02C_LOD_1 (1)",
                                    "TFF_Rock_Large_06A_LOD_1 (8)",
                                    "TFF_Rock_Large_06A_LOD_1 (9)",
                                    "TFF_Rock_Large_06A_LOD_1 (16)",
                                    "TFF_Rock_Large_06A_LOD_1 (14)",
                                    "TFF_Rock_Large_06A_LOD_1 (17)",
                                    "TFF_Rock_Large_06A_LOD_1 (18)",
                                    "TFF_Rock_Large_06A_LOD_1 (58)",
                                    "TFF_Rock_Large_06A_LOD_1 (31)",
                                    "TFF_Rock_Large_06A_LOD_1 (37)",
                                    "TFF_Rock_Large_06A_LOD_1 (38)",
                                };
                                if (objNames.Contains(obj.name))
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                    }
                }
            },
            {
                "Ripper", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = 0,
                    OriginY = 0,
                    BaseTilesX = 4,
                    BaseTilesY = 3,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 1)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if ((obj.name.StartsWith("SM_") || obj.name.ToLower().Contains("torch")) && obj.transform.position.y > 145f)
                                {
                                    obj.SetActive(false);
                                }
                                string[] objNames =
                                {
                                    "SM_Env_Tree_Large_02_LOD2",
                                    "SM_Env_Tree_Large_02_LOD2 (2)",
                                    "SM_Env_Tree_Giant_02_LOD1 (1)",
                                    "SM_Env_Tree_Giant_02_LOD1",
                                    "SM_Env_Tree_Large_02_LOD2 (1)",
                                };
                                if (objNames.Contains(obj.name))
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                        else if (zoomLevel == 2)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if ((obj.name.StartsWith("SM_") || obj.name.ToLower().Contains("torch")) && obj.transform.position.y > 135f)
                                {
                                    obj.SetActive(false);
                                }
                                if (obj.name.StartsWith("SM_Prop_Beam_03"))
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                    }
                }
            },
            {
                "Rockshade", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = 0,
                    OriginY = 0,
                    BaseTilesX = 4,
                    BaseTilesY = 4,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 1)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (obj.name.Contains("Roof"))
                                {
                                    obj.SetActive(false);
                                }
                                if (obj.name.Contains("Floor_Wood") && obj.transform.position.y > 115f)
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                        else if (zoomLevel == 2)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (obj.name.Contains("Floor_Wood"))
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                    }
                }
            },
            {
                "Rottenfoot", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = 0,
                    OriginY = 0,
                    BaseTilesX = 4,
                    BaseTilesY = 4,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            string[] objNames =
                            {
                                "SM_Env_Tree_Swamp_02_LOD2 (1)",
                                "SM_Env_Tree_Swamp_03_LOD1",
                                "SM_Env_Tree_Swamp_03_LOD1 (5)",
                            };
                            foreach (var objName in objNames)
                            {
                                var obj = GameObject.Find(objName);
                                obj?.SetActive(false);
                            }
                        }
                        else if (zoomLevel == 1)
                        {
                            string[] objNames =
                            {
                                "SM_Env_Tree_Swamp_02 (13)",
                                "SM_Env_Tree_Swamp_02_LOD2",
                                "SM_Env_Tree_Swamp_03 (17)",
                            };
                            foreach (var objName in objNames)
                            {
                                var obj = GameObject.Find(objName);
                                obj?.SetActive(false);
                            }
                        }
                    }
                }
            },
            {
                "SaltedStrand", new TileScreenshotter.TileShotterSettings {
                    ZoomLevels = 3,
                    OriginX = -64,
                    OriginY = 0,
                    BaseTilesX = 4,
                    BaseTilesY = 3,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 1)
                        {
                            var obj = GameObject.Find("TFF_Rock_Large_05A (3)");
                            obj?.SetActive(false);
                        }
                    }
                }
            },
            {
                "Silkengrass", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = -32,
                    OriginY = 0,
                    BaseTilesX = 5,
                    BaseTilesY = 6,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 1)
                        {
                            var obj = GameObject.Find("SM_Env_Tree_Giant_02_LOD2");
                            obj?.SetActive(false);
                        }
                    }
                }
            },
            {
                "Soluna", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = 0,
                    OriginY = 0,
                    BaseTilesX = 4,
                    BaseTilesY = 4,
                }
            },
            {
                "Stowaway", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = 135,
                    OriginY = 225,
                    BaseTilesX = 3,
                    BaseTilesY = 2,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 1)
                        {
                            string[] objNames =
                            {
                                "TFF_Rock_Large_03A",
                                "TFF_Rock_Large_03A (1)",
                                "TFF_Rock_Large_05A (15)",
                                "TFF_Rock_Large_05A (16)",
                                "TFF_Rock_Large_05A (18)",
                                "TFF_Rock_Large_06A (8)",
                                "TFF_Rock_Large_06A (9)",
                                "TFF_Rock_Large_06A (11)",
                                "TFF_Rock_Large_06A (10)",
                                "TFF_Oak_Tree_01C_LOD_1 (4)",
                                "TFF_Oak_Tree_01C_LOD_1 (5)",
                                "TFF_Pine_Tree_02A (13)"
                            };
                            foreach (var objName in objNames)
                            {
                                var obj = GameObject.Find(objName);
                                obj?.SetActive(false);
                            }
                        }
                    }
                }
            },
            {
                "Tutorial", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = -192,
                    OriginY = -192,
                    BaseTilesX = 2,
                    BaseTilesY = 2,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (obj.name.StartsWith("SM_Env_Ceiling_Stone_Flat_06"))
                                {
                                    obj.SetActive(false);
                                }
                                if (obj.name.StartsWith("SM_Env_Cave_Roof_01_DoubleSided"))
                                {
                                    obj.SetActive(false);
                                }
                                if (obj.name.StartsWith("SM_Env_Cave_Large_01 ("))
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                        else if (zoomLevel == 3)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (obj.name.Contains("Occuphage"))
                                {
                                    obj.SetActive(false);
                                }
                                if (obj.transform.position.x > 75f && obj.transform.position.y > 0f && obj.transform.position.z > 100f)
                                {
                                    if (obj.name.StartsWith("SM_"))
                                    {
                                        obj.SetActive(false);
                                    }
                                }
                            }
                        }
                    }
                }
            },
            {
                "Undercity", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = 0,
                    OriginY = 0,
                    BaseTilesX = 2,
                    BaseTilesY = 2,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                string[] objNames =
                                {
                                    "TFF_Rock_Large_06A_LOD_1 (28)", "TFF_Rock_Large_06A_LOD_1 (11)", "TFF_Rock_Large_06A_LOD_1 (10)",
                                    "TFF_Rock_Large_06A_LOD_1 (27)", "TFF_Rock_Large_06A_LOD_1 (68)", "TFF_Rock_Large_06A_LOD_1 (71)",
                                    "TFF_Rock_Large_06A_LOD_1 (70)", "TFF_Rock_Large_06A_LOD_1 (69)", "TFF_Rock_Large_06A_LOD_1 (67)",
                                    "TFF_Rock_Large_06A_LOD_1 (66)", "TFF_Rock_Large_06A_LOD_1 (72)", "TFF_Rock_Large_06A_LOD_1 (61)",
                                    "TFF_Rock_Large_06A_LOD_1 (62)", "TFF_Rock_Large_06A_LOD_1 (73)", "TFF_Rock_Large_06A_LOD_1 (63)",
                                    "TFF_Rock_Large_06A_LOD_1 (64)", "TFF_Rock_Large_06A_LOD_1 (65)", "TFF_Rock_Large_06A_LOD_1 (9)",
                                    "TFF_Rock_Large_06A_LOD_1 (42)", "TFF_Rock_Large_06A_LOD_1 (43)", "TFF_Rock_Large_06A_LOD_1 (45)",
                                    "TFF_Rock_Large_06A_LOD_1 (44)", "TFF_Rock_Large_06A_LOD_1 (46)", "TFF_Rock_Large_06A_LOD_1 (47)",
                                    "SM_Env_Stalagmite_06 (3)", "TFF_Rock_Large_06A_LOD_1 (74)", "SM_Rock_CaveEntrance_02 (2)",
                                    "SM_Rock_CaveEntrance_02", "SM_Env_Stalagmite_06 (1)", "SM_Env_Stalagmite_06 (2)",
                                    "SM_Env_Stalagmite_01 (4)", "SM_Env_Stalagmite_01 (3)", "SM_Env_Stalagmite_06",
                                    "SM_Env_Rock_Cliff_03 (1)", "SM_Env_Rock_Cliff_03", "SM_Env_Stalagmite_05",
                                    "TFF_Rock_Large", "SM_Rock_CaveEntrance_02 (1)", "SM_Rock_CaveEntrance_02 (3)",
                                };
                                if (objNames.Contains(obj.name))
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                    }
                }
            },
            {
                "Underspine", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = 0,
                    OriginY = 0,
                    BaseTilesX = 3,
                    BaseTilesY = 3,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (obj.name.StartsWith("SM_Rock_Cluster_Large_02"))
                                {
                                    obj.SetActive(false);
                                }
                                if (obj.name.Equals("SM_Env_Rock_Pile_03"))
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                        else if (zoomLevel == 2)
                        {
                            string[] objNames =
                            {
                                "SM_Env_Rock_Cliff_03 (83)",
                                "SM_Env_Rock_Cliff_03 (89)",
                            };
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (objNames.Contains(obj.name))
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                    }
                }
            },
            {
                "Vitheo", new TileScreenshotter.TileShotterSettings {
                    ZoomLevels = 4,
                    BaseTilesX = 2,
                    BaseTilesY = 2,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 1)
                        {
                            var obj = GameObject.Find("TFF_Oak_Tree_01A (1)");
                            obj?.SetActive(false);
                        }
                    }
                }
            },
            {
                "VitheosEnd", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = 64,
                    OriginY = 64,
                    BaseTilesX = 2,
                    BaseTilesY = 2,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                string[] objNames =
                                {
                                    "SM_Bld_Castle_Wall_01 (184)",
                                    "SM_Bld_Castle_Wall_01 (183)",
                                    "SM_Bld_Castle_Wall_01 (182)",
                                    "SM_Bld_Castle_Wall_01 (188)",
                                    "SM_Bld_Castle_Wall_01 (187)",
                                    "SM_Bld_Castle_Wall_01 (186)",
                                    "SM_Bld_Castle_Wall_01 (185)",
                                    "SM_Bld_Castle_Wall_01 (181)",
                                    "SM_Bld_Beam_01",
                                    "SM_Bld_Wall_Beam_01 (28)",
                                    "SM_Bld_Wall_Beam_01 (27)",
                                    "SM_Bld_Wall_Beam_01 (26)",
                                    "SM_Bld_Wall_Beam_01 (25)",
                                    "SM_Bld_Castle_Wall_01 (8)",
                                    "SM_Bld_Castle_Wall_01 (9)",
                                    "SM_Bld_Castle_Wall_01 (11)",
                                    "SM_Bld_Castle_Wall_01 (10)",
                                    "SM_Bld_Castle_Wall_01 (174)",
                                    "SM_Bld_Castle_Wall_01 (175)",
                                    "SM_Bld_Castle_Wall_01 (176)",
                                    "SM_Bld_Castle_Wall_01 (177)",
                                    "SM_Bld_Castle_Wall_01 (173)",
                                    "SM_Bld_Castle_Wall_01 (178)",
                                    "SM_Bld_Castle_Wall_01 (179)",
                                    "SM_Bld_Castle_Wall_01 (180)",
                                };
                                if (objNames.Contains(obj.name))
                                {
                                    obj.SetActive(false);
                                }
                                if (obj.name.Contains("House_StoneArch") && obj.transform.position.z < 125)
                                {
                                    obj.SetActive(false);
                                }
                                if (obj.transform.position.y > 19 && obj.transform.position.x < 210)
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                        else if (zoomLevel == 3)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (obj.transform.position.y > -29)
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                    }
                }
            },
            {
                "Windwashed", new TileScreenshotter.TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = 190,
                    OriginY = -128,
                    BaseTilesX = 4,
                    BaseTilesY = 4,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            string[] objNames =
                            {
                                "SM_Env_Rock_Cliff_03 (68)",
                                "SM_Env_Rock_Cliff_03 (70)",
                                "SM_Env_Rock_Cliff_03 (69)",
                            };
                            foreach (var objName in objNames)
                            {
                                var obj = GameObject.Find(objName);
                                obj?.SetActive(false);
                            }
                        }
                    }
                }
            },
        };

    public static void Run(bool dryRun = true)
    {
        var sceneName = SceneManager.GetActiveScene().name;
        if (SceneConfigs.TryGetValue(sceneName, out var settings))
        {
            Debug.Log($"Using scene config for {sceneName}: {settings}");
        }
        else
        {
            settings = new TileShotterSettings();
            Debug.Log($"No scene config found for {sceneName}, using default settings.");
        }

        Run(settings, dryRun);
    }

    public static void Run(TileShotterSettings settings, bool dryRun = true)
    {
        UnityEngine.Time.timeScale = 0f;

        Camera cam = Camera.main;
        Scene scene = SceneManager.GetActiveScene();
        
        WorldFogController fogController = UnityEngine.Object.FindObjectOfType<WorldFogController>();
        fogController?.gameObject.SetActive(false);

        if (dryRun)
        {
            var z = settings.ZoomLevels - 1;
            var tilesX = settings.BaseTilesX << z;
            var tilesY = settings.BaseTilesY << z;
            var unitsPerTile = settings.TileWorldSize / (1 << z); // Adjust if you want tile size to decrease with zoom

            cam.orthographic = true;
            cam.nearClipPlane = 0.1f;
            cam.farClipPlane = 2000f;
            cam.useOcclusionCulling = false;

            // Center camera over the tiling area
            var areaWidth = tilesX * unitsPerTile;
            var areaHeight = tilesY * unitsPerTile;
            cam.transform.position = new Vector3(settings.OriginX + areaWidth / 2f, settings.CameraHeight, settings.OriginY + areaHeight / 2f);
            cam.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
            cam.orthographicSize = Mathf.Max(areaWidth, areaHeight) / 2f;

            var outlineY = settings.CameraHeight / 2;
            var parent = new GameObject("TileOutlines");

            for (var x = 0; x < tilesX; x++)
            {
                for (var y = 0; y < tilesY; y++)
                {
                    var centerX = settings.OriginX + unitsPerTile * (x + 0.5f);
                    var centerZ = settings.OriginY + unitsPerTile * (y + 0.5f);
                    var half = unitsPerTile / 2f;

                    var corners = new Vector3[5]
                    {
                        new Vector3(centerX - half, outlineY, centerZ - half),
                        new Vector3(centerX + half, outlineY, centerZ - half),
                        new Vector3(centerX + half, outlineY, centerZ + half),
                        new Vector3(centerX - half, outlineY, centerZ + half),
                        new Vector3(centerX - half, outlineY, centerZ - half)
                    };

                    var go = new GameObject($"TileOutline_{x}_{y}");
                    go.transform.parent = parent.transform;
                    var lr = go.AddComponent<LineRenderer>();
                    lr.positionCount = 5;
                    lr.SetPositions(corners);
                    lr.startWidth = lr.endWidth = 2f;
                    lr.material = new Material(Shader.Find("Sprites/Default"));
                    lr.startColor = lr.endColor = Color.red;
                    lr.useWorldSpace = true;

                    GameObject textObject = new GameObject($"TileText_{x}_{y}");
                    textObject.transform.parent = parent.transform;
                    textObject.transform.position = new Vector3(centerX, outlineY + 5f, centerZ);

                    var leafletX = x;
                    var leafletY = -(y + 1);

                    var textMesh = textObject.AddComponent<TextMesh>();
                    textMesh.text = $"z={z}\n{leafletX},{leafletY}";
                    textMesh.fontSize = 64;
                    textMesh.characterSize = unitsPerTile / 64f;
                    textMesh.anchor = TextAnchor.MiddleCenter;
                    textMesh.alignment = TextAlignment.Center;
                    textMesh.color = Color.white;
                    textObject.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
                }
            }

            Debug.Log("Dry run: drew tile outlines and set camera to view the full area, with tile indices.");
        }
        else
        {
            if (settings.OutputRoot == null)
            {
                Debug.LogError("OutputRoot is null, cannot run screenshotter.");
                return;
            }

            for (var z = 0; z < settings.ZoomLevels; z++)
            {
                settings.PreProcess?.Invoke(z);

                var tilesX = settings.BaseTilesX << z;
                var tilesY = settings.BaseTilesY << z;
                var unitsPerTile = settings.TileWorldSize / (1 << z);

                cam.orthographic = true;
                cam.nearClipPlane = 0.1f;
                cam.farClipPlane = 2000f;
                cam.useOcclusionCulling = false;

                var rt = new RenderTexture(settings.TilePixelSize, settings.TilePixelSize, 24);
                var tex = new Texture2D(settings.TilePixelSize, settings.TilePixelSize, TextureFormat.RGB24, false);

                for (var x = 0; x < tilesX; x++)
                {
                    for (var y = 0; y < tilesY; y++)
                    {
                        var centerX = settings.OriginX + unitsPerTile * (x + 0.5f);
                        var centerZ = settings.OriginY + unitsPerTile * (y + 0.5f);

                        cam.transform.position = new Vector3(centerX, settings.CameraHeight, centerZ);
                        cam.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
                        cam.orthographicSize = unitsPerTile / 2f;

                        var leafletX = x;
                        var leafletY = -(y + 1);

                        var dir = $"{settings.OutputRoot}/{scene.name}/{z}/{leafletX}";
                        Directory.CreateDirectory(dir);
                        var path = $"{dir}/{leafletY}.jpg";

                        if (File.Exists(path))
                        {
                            Debug.Log($"Tile already exists, skipping: {path}");
                            continue;
                        }

                        cam.targetTexture = rt;
                        cam.Render();

                        RenderTexture.active = rt;
                        tex.ReadPixels(new Rect(0, 0, settings.TilePixelSize, settings.TilePixelSize), 0, 0);
                        tex.Apply();
                        var bytes = tex.EncodeToJPG(85);
                        File.WriteAllBytes(path, bytes);
                        RenderTexture.active = null;
                        Debug.Log($"Saved tile: {path}");
                    }
                }

                cam.targetTexture = null;
                UnityEngine.Object.DestroyImmediate(rt);
                UnityEngine.Object.DestroyImmediate(tex);

                settings.PostProcess?.Invoke(z);

                Debug.Log($"Zoom level {z} complete.");
            }

            Debug.Log("Screenshot run complete.");
        }
    }
}
