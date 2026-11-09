# B7 戶 3D 模型（rev.4 平面圖為準）

| 檔案 | 用途 | 單位 / 座標 |
|---|---|---|
| `B7_model.glb` | 通用 3D（Blender、Rhino 8、Windows 3D 檢視器、網頁） | m，Y 軸朝上 |
| `B7_model.obj` + `B7_model.mtl` | 通用網格（3ds Max、Blender、Rhino…），兩檔須放同一資料夾 | m，Y 軸朝上 |
| `B7_model.dae` | SketchUp：檔案 → 匯入 → Collada | m，Z 軸朝上 |
| `B7_model_3D.dxf` | AutoCAD（MESH 網格，圖層 3D-WALL / 3D-SLAB / 3D-COLUMN / 3D-BEAM / 3D-STAIR…） | cm，Z 軸朝上 |
| `B7_model.ifc` | Revit / ArchiCAD（IFC4，分 1F/2F/3F/RF 樓層；牆、版、柱、梁、樓梯、門窗各自為構件） | mm，Z 軸朝上 |
| `B7_model.usdz` | iPhone / iPad：點開即可 3D 檢視或 AR | m，Y 軸朝上 |
| `preview/` | 外觀與各層剖切預覽圖 | — |

座標原點：X=0 為西側地界線（私設通路側），Y=0 為 B6/B7 分戶牆中心線，Z=0 為 GL。

## 建模依據與假設
- 高程：GL±0、1FL+30、2FL+390、3FL+710、RFL+1030；女兒牆頂 +1170。
- 樓板厚 15；牆厚一律 15（中心線依平面尺寸鍊）；梁 30×60（梁頂平樓板頂）。
- 柱：依圖面比例繪製，**非實際尺寸**。
- 樓梯：1F→2F 19 級 @18.95（起步 2 階扇形踏步＋11 級＋平台＋6 級）；2F→3F 17 級 @18.82（9 級＋平台＋8 級）；踏面 25。
- 門窗寬度依圖面比例量取；窗台／窗頂高度為假設值（W 窗台 90～150、門頂 210～230），請依門窗表修正。
- 一樓廁所位於樓梯下方，西牆高度隨樓梯底板降低。
- 衛浴、廚具為示意量體。
