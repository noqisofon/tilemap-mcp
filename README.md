# tilemap-mcp

AI エージェントが「タイル名 + 座標」でドット絵のマップやスプライトを組み立てるための MCP サーバー。
プレビュー確認はもちろん、本格的なゲーム制作（Godot, Unity, Phaser 等）やアセット制作にも対応しています。

- **状態管理**: タイル定義やマップ配置は JSON で永続化
- **動的レンダリング**: 編集のたびに PNG や GIF を生成してエージェントが「見て確認」
- **ゲーム開発連携**: 当たり判定（collision）やタグを含むスプライトシート・アトラス JSON のエクスポートに対応

## セットアップ

Python 3.10 以上。`mcp` は 1.x / 2.x のどちらでも動きます。

### 1. インストール（どちらか 1 つ）

```bash
# A: uv（推奨）— このリポジトリのフォルダで
uv sync

# B: pip — 仮想環境を作ってから
python -m venv .venv
.venv\Scripts\activate          # macOS / Linux: source .venv/bin/activate
pip install -e .
```

### 2. 動作確認（任意）

```bash
python -m tilemap_mcp.demo             # demo_out/room.png に部屋を描画
python tests/tilemap_mcp/test_core.py  # コアロジックの回帰テスト
python tests/tilemap_mcp/test_mcp.py   # MCP の stdio 経由で全ツールを呼ぶ統合テスト
```

## MCP に登録する

### 先に決めること: 保存先 `TILEMAP_DIR`

プロジェクトの JSON、`render.png`、アトラス、GIF はすべてここに出力されます。**絶対パスで指定してください。**

エージェント（AI）が出力先を自由に指定することはできません。サーバーが書き込むのは、常にこのフォルダの中だけです（エージェントの勘違いや、読み込んだ内容に仕込まれた指示で、他の場所のファイルを上書きされないようにするためです）。ゲームのプロジェクトへ持っていくときは、エージェントがファイル操作で、このフォルダから必要なファイルをコピーします。保存先は、サーバーが接続時にエージェントへ伝える説明文にも入れてあります（クライアントによっては、モデルに渡らない場合があります）。

```
<TILEMAP_DIR>/
  project.json              いまのプロジェクト（起動時に自動で読み込み）
  projects/<名前>.json      save_project_as で名前をつけて保存したもの
  render.png                name なしの render（毎回上書き）
  renders/<name>.png        name つきの render（上書きされない）
  atlas.png / atlas.json / tiled_map.json   name なしの export_atlas
  exports/<name>/           name つきの export_atlas（マップやゲームごとに分けられる）
```

相対パス（`./tilemap_data`）や未指定だと、「MCP クライアントがサーバーを起動したフォルダ」の下になります。起動場所はクライアントによって違うので、データがどこに出たか分からなくなります（この場合、起動時にログへ警告を出します）。

### uv で登録（推奨）

`--directory` にこのリポジトリを指定すると、クライアントがどのフォルダから起動しても動きます。

```bash
claude mcp add tilemap -e TILEMAP_DIR=C:/Users/you/tilemap_data -- uv --directory C:/Users/you/Projects/tilemap-mcp run tilemap-mcp
```

Antigravity / Cline / Cursor などの `mcp.json` 形式：

```json
{
  "mcpServers": {
    "tilemap": {
      "command": "uv",
      "args": ["--directory", "C:/Users/you/Projects/tilemap-mcp", "run", "tilemap-mcp"],
      "env": { "TILEMAP_DIR": "C:/Users/you/tilemap_data" }
    }
  }
}
```

### pip（仮想環境）で登録

`pip install -e .` 済みの**仮想環境の python を絶対パスで**指定します（この場合 `PYTHONPATH` は不要）。

```json
{
  "mcpServers": {
    "tilemap": {
      "command": "C:/Users/you/Projects/tilemap-mcp/.venv/Scripts/python.exe",
      "args": ["-m", "tilemap_mcp"],
      "env": { "TILEMAP_DIR": "C:/Users/you/tilemap_data" }
    }
  }
}
```

macOS / Linux では `command` を `/path/to/tilemap-mcp/.venv/bin/python` にします。

パスの書き方: JSON の中では `\` を `\\` と重ねるか、`/` を使います。`C:/Users/...` は Windows でもそのまま通ります。

### 動いているか確認する

1. エージェントに「tilemap の `list_tiles` を呼んで」と頼みます。返答の末尾に `data_dir=...` が出れば、サーバーは起動していて、データの出力先もそこです。
2. クライアントの MCP ログ（stderr）にも、起動時に `[tilemap-mcp] data dir: ...` が出ます。

### 困ったとき

| 症状                                       | 原因と対処                                                                                                                                                                                                                                                 |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `No module named tilemap_mcp` で起動しない | `command` が仮想環境の python ではないか、`pip install -e .` をしていません。`PYTHONPATH=src` のような相対パスは、クライアントがこのリポジトリ直下から起動しない限り効かないので使わないでください。上の uv か、仮想環境の python の絶対パスで登録します。 |
| 出力したファイルが見つからない             | `list_tiles` の `data_dir` を確認します。ログに「relative path」の警告が出ていたら、`TILEMAP_DIR` を絶対パスにします。                                                                                                                                     |
| 前回の続きから始まる                       | 起動時に `data_dir` の `project.json` を読み込みます。まっさらから始めるときは `new_project` を呼びます（別名で残したいときは先に `save_project_as`）。                                                                                                    |
| 初回の起動が遅い（`uv` の場合）            | 初回は依存パッケージの取得に時間がかかることがあります。先にターミナルで `uv sync` しておくと安全です。                                                                                                                                                    |

## 利用可能なツール一覧

### 1. プロジェクト管理
- `new_project(tile_size=16)`: 新規プロジェクト作成（4〜64px）
- `save_project_as(name)`: 現在のマップ・タイルを名前付きで保存（`projects/{name}.json`）
- `load_project(name)`: 保存済みプロジェクトの読み込み
- `list_projects()`: 保存済みプロジェクト一覧

### 2. タイルの定義・編集・変形
- `define_tile(name, palette, rows, solid=None, tags=None)`: 1文字1ピクセルのテキストアートでタイル定義（`.` は透明）
- `clone_tile(src_name, new_name, flip_h=False, flip_v=False, rotate=0)`: 既存タイルの左右反転・上下反転・90/180/270度回転（キャラの向きや壁の角、階段の向きに便利）
- `import_tile_from_file(name, file_path, solid=None, tags=None)`: 1枚のPNG画像を丸ごと1タイルとして取り込み（パレット・文字アートを自動抽出）
- `inspect_tileset(file_path, tile_size=None, margin=0, spacing=0, background=None, row_range=None, col_range=None, scale=None)`: **既存のスプライトシートを見る。** 行・列番号つきの拡大画像と、中身のあるマスの一覧を返す（空マスは暗く表示）。「どのマスに何の絵があるか」を、画素を数えずに画像で判断できる。`background="#000000"` で黒背景を空扱い、`row_range` / `col_range` で大きなシートの一部だけを表示
- `import_tile_from_sheet(name, file_path, row, col, tile_size=None, margin=0, spacing=0, transparent_color=None, fit="exact", solid=None, tags=None)`: シートの (row, col) のマス1つを取り込む。`transparent_color="#000000"` で背景を透明にして、床の上に重ねられるようにする
- `slice_tileset(file_path, prefix="tile", solid=None, tile_size=None, margin=0, spacing=0, background=None, skip_empty=False, transparent_color=None, fit="exact", row_range=None, col_range=None, max_tiles=1000)`: シートを `<prefix>_<row>_<col>` の名前で一括登録。余白（margin）・間隔（spacing）つきのシートに対応

  シートのタイルサイズとプロジェクトの `tile_size` が違う場合、`fit="exact"`（既定）は黙って拡縮せずにエラーで対処法を返す。`fit="pad"` は小さいタイルを中央に置き、`fit="scale"` は最近傍で拡縮する。通常は `new_project(tile_size=シートのタイルサイズ)` で揃えるのがおすすめ。
  例（12px タイル・外周1px・間隔1px のシート）: `tile_size=12, margin=1, spacing=1`
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
- `render(scale=4, layers=None, show_grid=False, view_rect=None, fog_of_war=False, light_sources=None, name=None)`:
  - マップ全体または **`view_rect=[x, y, w, h]` によるカメラ視野** を PNG 描画
  - **`fog_of_war=True` と `light_sources` による視野・ダンジョンの暗闇表現**
  - `show_grid=True` で座標付きグリッドを描画
  - `name="room_a"` を渡すと `renders/room_a.png` に残る（渡さないと `render.png` を毎回上書き）
- `render_animation(frames, scale=4, duration=200, gif_name='animation.gif')`: 各フレームのタイル変化を GIF アニメーションとして生成
- `export_atlas(columns=8, name=None)`: 全タイルのスプライトシート（`atlas.png`）、タイルのプロパティ（`atlas.json`）、および **Phaser / Bevy 等で直接読み込める Tiled Map Editor 形式（`tiled_map.json`）** を出力。`name="dungeon_b1"` を渡すと `exports/dungeon_b1/` に出力され、別のマップの書き出しと上書きし合わない
