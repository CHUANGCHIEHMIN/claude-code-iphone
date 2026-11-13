# B7 1F 入口視角渲染

| 檔案 | 說明 |
|---|---|
| `B7_1F_entry_view.jpg` | three.js 即時渲染（初版） |
| `B7_1F_entry_view_cycles.jpg` | Blender Cycles 路徑追蹤，程式化材質 |
| `B7_1F_entry_view_photoreal.jpg` | Cycles + Poly Haven CC0 實拍貼圖、家具模型、HDRI，加相機後製 |

## 重現步驟（`../src/`）
1. `interior_render.html` + `iexport.js`：在 three.js 建立家具配置並匯出 GLB；`glb_fix.py` 修正 glTF volume 擴充。
2. `ph_get.py <素材資料夾>`：自 Poly Haven（CC0）下載模型、貼圖、HDRI（素材不放入 repo）。
3. `b7_cycles2.py <glb> <out.png> 1920 1080 256 16 10 0.8 <素材資料夾>`：Cycles 渲染（需 `pip install bpy`）。
4. `post.py <out.png> <out.jpg>`：柔光、暗角、顆粒後製。

素材來源：Poly Haven（polyhaven.com），CC0 授權。
