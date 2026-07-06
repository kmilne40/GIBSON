from pathlib import Path
def list_maps(asset_root):
    return sorted(p.name for p in Path(asset_root).glob("*.bms"))
