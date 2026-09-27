# tilemap-mcp

AI エージェントが「タイル名 + 座標」でドット絵のマップやスプライトを組み立てるための MCP サーバー。
プレビュー確認はもちろん、本格的なゲーム制作（Godot, Unity, Phaser 等）やアセット制作にも対応しています。

- **状態管理**: タイル定義やマップ配置は JSON で永続化
- **動的レンダリング**: 編集のたびに PNG や GIF を生成してエージェントが「見て確認」
- **ゲーム開発連携**: 当たり判定（collision）やタグを含むスプライトシート・アトラス JSON のエクスポートに対応

## セットアップ

`mcp>=1.0` (mcp 1.x FastMCP / mcp 2.x MCPServer の両方) に対応しています。

```bash
# 依存関係インストール (uv または pip)
uv sync
# または
pip install -r requirements.txt

# 動作検証
python test_core.py  # コアロジック・回帰テスト (7件)
python test_mcp.py   # MCP stdio 経由で全27ツールの統合テスト
python demo.py       # demo_out/ に部屋とスプライトを描画
```

## MCP 設定例

### パッケージインストール（推奨）
```bash
pip install .
```
インストール後はコマンド名だけで登録できます：
```bash
claude mcp add tilemap -e TILEMAP_DIR=./tilemap_data -- tilemap-mcp
```

### 直接スクリプト指定（リポジトリのまま使う場合）
```bash
claude mcp add tilemap -e TILEMAP_DIR=./tilemap_data -- python C:\Users\nedri\Projects\tilemap-mcp\server.py
```

### Antigravity / Cline / Cursor 等 (mcp.json)
```json
{
  "mcpServers": {
    "tilemap": {
      "command": "python",
      "args": ["C:/Users/nedri/Projects/tilemap-mcp/server.py"],
      "env": {
        "TILEMAP_DIR": "./tilemap_data"
      }
    }
  }
}
```

## 利用可能なツール一覧

### 1. プロジェクト管理
- `new_project(tile_size=16)`: 新規プロジェクト作成（4〜64px）
- `save_project_as(name)`: 現在のマップ・タイルを名前付きで保存（`projects/{name}.json`）
- `load_project(name)`: 保存済みプロジェクトの読み込み
- `list_projects()`: 保存済みプロジェクト一覧

### 2. タイルの定義・編集・変形
- `define_tile(name, palette, rows, solid=None, tags=None)`: 1文字1ピクセルのテキストアートでタイル定義（`.` は透明）
- `clone_tile(src_name, new_name, flip_h=False, flip_v=False, rotate=0)`: 既存タイルの左右反転・上下反転・90/180/270度回転（キャラの向きや壁の角、階段の向きに便利）
- `import_tile_from_file(name, file_path, solid=None, tags=None)`: 既存のPNG画像からパレット・文字アートを自動抽出して取り込み
- `slice_tileset(file_path, prefix="tile", solid=None)`: スプライトシート画像をタイルサイズごとに切り出して一括登録
- `set_tile_properties(name, solid=None, tags=None, meta=None)`: タイルに当たり判定（壁など）やタグ・カスタム情報を設定
- `get_tile_properties(name)`: タイルのプロパティ取得
- `preview_tile(name, scale=16)`: 市松模様背景でタイルを拡大プレビュー
- `list_tiles()`: プロジェクトの概要・登録タイル一覧

### 3. マップの構築・編集
- `create_map(width, height, layers=None)`: 空のマップ作成（デフォルトレイヤー: `["ground", "objects"]`）
- `resize_map(new_width, new_height, offset_x=0, offset_y=0)`: **既存の配置を壊さずにマップを拡張・移動**（部屋から通路を伸ばす際に必須）
- `add_layer(name)`: 上位レイヤーを追加
- `place(layer, x, y, tile)`: 1セル配置（tile=null で消去）
- `fill(layer, x, y, w, h, tile)`: 矩形塗りつぶし
- `border(layer, x, y, w, h, tile)`: 部屋の外周壁を作成
- `carve_corridor(x1, y1, x2, y2, width=2, floor_tile='stone', wall_tile='brick')`: **L字通路を掘削**（床を敷き、障害物を消去し、周囲に壁を自動配置）
- `set_map_from_ascii(layer, grid, legend, x=0, y=0)`: アスキーアートでまとめてスタンプ配置
- `get_cell(x, y)`: 指定座標の各レイヤーのタイル名を取得
- `dump_layer_ascii(layer)`: レイヤー内容をアスキーアートとして取得

### 4. プレハブ（スタンプ）
- `save_prefab(name, x, y, w, h, layers=None)`: 特定の領域（宝箱セット、小部屋など）を再利用可能なプレハブとして保存
- `stamp_prefab(name, x, y, ignore_empty=True)`: 保存したプレハブを指定座標に一括配置

### 5. レンダリング・エクスポート
- `render(scale=4, layers=None, show_grid=False, view_rect=None, fog_of_war=False, light_sources=None)`:
  - マップ全体または **`view_rect=[x, y, w, h]` によるカメラ視野** を PNG 描画
  - **`fog_of_war=True` と `light_sources` による視野・ダンジョンの暗闇表現**
  - `show_grid=True` で座標付きグリッドを描画
- `render_animation(frames, scale=4, duration=200, gif_name='animation.gif')`: 各フレームのタイル変化を GIF アニメーションとして生成
- `export_atlas(columns=8)`: 全タイルのスプライトシート（`atlas.png`）と、各タイルの座標・当たり判定情報（`atlas.json`）を出力
